"""Fills the SQLite database with demo users, cars, bookings and payments.

    python manage.py seed           # adds demo data (skips if it already exists)
    python manage.py seed --reset   # deletes the demo users (and their cars) first, then adds again

Demo logins (phone / password):  555000001 / demo-pass-123   and   555000002 / demo-pass-123

Photos: put real car photos (.png .jpg .jpeg .webp) in a folder called `seed_photos`
next to manage.py and they are used in alphabetical order, 3 per car. Without that
folder, simple drawn car pictures in the site's colours are used instead.
The "Nissan Figaro" listing always uses the real photo from static/portal/img/hero-car.webp.
"""
import random
import struct
import zlib
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import Car, Favorite, Notification, Payment, Rental, User

PASSWORD = "demo-pass-123"
PHOTO_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
FIGARO_PHOTO = Path(__file__).resolve().parents[2] / "static" / "portal" / "img" / "hero-car.webp"

USERS = [
    ("555000001", "ნინო", "ბერიძე", "nino@example.com"),
    ("555000002", "გიორგი", "კაპანაძე", "giorgi@example.com"),
]

# brand, model, year, price, seats, transmission, city, fuel, (lat, lng) or None
CARS = [
    ("Nissan", "Figaro", 1991, 70, 4, "automatic", "თბილისი", 40, (41.6941, 44.8015)),
    ("Mercedes", "E320", 2015, 90, 5, "automatic", "თბილისი", 80, (41.7151, 44.8271)),
    ("Toyota", "Prius", 2012, 50, 5, "automatic", "თბილისი", 45, (41.7090, 44.7930)),
    ("BMW", "X5", 2018, 150, 5, "tiptronic", "ბათუმი", 85, (41.6168, 41.6367)),
    ("Hyundai", "H1", 2010, 110, 8, "manual", "ბათუმი", 75, None),
    ("Honda", "Fit", 2008, 40, 4, "automatic", "ქუთაისი", 40, (42.2679, 42.6946)),
    ("Ford", "Transit", 2005, 120, 9, "manual", "რუსთავი", 80, None),
    ("Lexus", "RX 350", 2016, 140, 5, "automatic", "თბილისი", 72, (41.6938, 44.8015)),
    ("Volkswagen", "Golf", 1999, 35, 5, "manual", "გორი", 55, None),
    ("Mitsubishi", "Delica", 2003, 100, 7, "automatic", "ბორჯომი", 75, (41.8394, 43.3792)),
    ("Subaru", "Forester", 2014, 80, 5, "automatic", "ბაკურიანი", 60, None),
]

# Site palette: (background, car body, windows)
MERINO, PAPER, ROCK, ROCK_SOFT = (245, 238, 221), (251, 247, 238), (132, 179, 206), (211, 228, 238)
INK = (14, 59, 83)
PALETTES = [
    (ROCK_SOFT, ROCK, PAPER),
    (MERINO, ROCK, PAPER),
    (PAPER, ROCK, ROCK_SOFT),
    (ROCK, PAPER, ROCK_SOFT),
    (MERINO, ROCK_SOFT, PAPER),
]


# ---------------------------------------------------------------------------
# Tiny PNG writer + a drawn car picture (no Pillow, no AI, just geometry)
# ---------------------------------------------------------------------------

def _png(width, height, rows):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + row for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def make_png(color, width=320, height=240):
    """A solid-color PNG (used by the tests)."""
    return _png(width, height, [bytes(color) * width] * height)


def draw_car(bg, body, glass, width=480, height=360):
    """A flat side-view car on grid paper, in the site's colours."""
    W, H = width, height
    grid_line = tuple(max(c - 14, 0) for c in bg)
    shadow = tuple(max(c - 30, 0) for c in bg)

    def in_round_rect(x, y, x0, y0, x1, y1, r):
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        cx = min(max(x, x0 + r), x1 - r)
        cy = min(max(y, y0 + r), y1 - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    def in_trapezoid(x, y, top, bottom, top_l, top_r, bot_l, bot_r):
        if not top <= y <= bottom:
            return False
        t = (y - top) / (bottom - top)
        return top_l + (bot_l - top_l) * t <= x <= top_r + (bot_r - top_r) * t

    wheels = [(0.29 * W, 0.70 * H), (0.71 * W, 0.70 * H)]
    tire_r, hub_r = 0.085 * W, 0.04 * W

    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            color = grid_line if (x % 24 == 0 or y % 24 == 0) else bg
            if ((x - 0.5 * W) / (0.40 * W)) ** 2 + ((y - 0.79 * H) / (0.035 * H)) ** 2 <= 1:
                color = shadow
            if in_trapezoid(x, y, 0.33 * H, 0.52 * H, 0.36 * W, 0.62 * W, 0.26 * W, 0.74 * W):
                color = body
                if in_trapezoid(x, y, 0.365 * H, 0.50 * H, 0.38 * W, 0.60 * W, 0.30 * W, 0.70 * W) \
                        and abs(x - 0.495 * W) > 0.008 * W:
                    color = glass
            if in_round_rect(x, y, 0.12 * W, 0.50 * H, 0.88 * W, 0.72 * H, 0.06 * W):
                color = body
                if abs(y - 0.585 * H) < 0.006 * H and 0.18 * W < x < 0.82 * W:
                    color = glass                                   # side stripe
                if (x - 0.855 * W) ** 2 + (y - 0.56 * H) ** 2 <= (0.018 * W) ** 2:
                    color = MERINO                                  # headlight
            for wx, wy in wheels:
                d = (x - wx) ** 2 + (y - wy) ** 2
                if d <= tire_r ** 2:
                    color = INK                           # tyre: thin dark outline-like detail
                    if d <= hub_r ** 2:
                        color = PAPER
            row += bytes(color)
        rows.append(bytes(row))
    return _png(W, H, rows)


def photo_files():
    """Real photos from ./seed_photos, if that folder exists."""
    folder = Path(settings.BASE_DIR) / "seed_photos"
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES)


class Command(BaseCommand):
    help = "Adds demo users, cars, bookings and payments to the database."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete demo users first")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        phones = [u[0] for u in USERS]
        if reset:
            User.objects.filter(phone__in=phones).delete()  # cascades to their cars, bookings ...
        elif User.objects.filter(phone__in=phones).exists():
            self.stdout.write("Demo data already exists (use --reset to recreate).")
            return

        users = [
            User.objects.create_user(phone, PASSWORD, first_name=first, last_name=last, email=email)
            for phone, first, last, email in USERS
        ]

        real_photos = photo_files()
        drawn = {}  # palette index -> PNG bytes (each picture is drawn once)

        cars = []
        for i, (brand, model, year, price, seats, trans, city, fuel, loc) in enumerate(CARS):
            car = Car(
                owner=users[i % 2], brand=brand, model=model, year=year, price=price,
                capacity=seats, transmission=trans, city=city, fuel_capacity=fuel,
                latitude=loc[0] if loc else None, longitude=loc[1] if loc else None,
            )
            for n, field in enumerate(("image1", "image2", "image3")):
                name = f"{brand}-{model}-{n + 1}".replace(" ", "_")
                if model == "Figaro" and FIGARO_PHOTO.exists():
                    content, ext = FIGARO_PHOTO.read_bytes(), ".webp"
                elif real_photos:
                    src = real_photos[(i * 3 + n) % len(real_photos)]
                    content, ext = src.read_bytes(), src.suffix.lower()
                else:
                    key = (i + n) % len(PALETTES)
                    if key not in drawn:
                        drawn[key] = draw_car(*PALETTES[key])
                    content, ext = drawn[key], ".png"
                getattr(car, field).save(name + ext, ContentFile(content), save=False)
            car.save()
            cars.append(car)

        # Bookings in the past, right now and in the future, so the calendar,
        # "popular cars", the profile tabs and notifications all have something to show.
        rng = random.Random(42)
        today = date.today()
        bookings = 0
        for car in cars[:7]:
            renter = users[1] if car.owner == users[0] else users[0]
            for offset, length in rng.sample([(-30, 3), (-12, 2), (-1, 3), (4, 2), (9, 4), (20, 5)], 3):
                start = today + timedelta(days=offset)
                end = start + timedelta(days=length - 1)
                total = car.price * length
                rental = Rental.objects.create(
                    user=renter, car=car, start_date=start, end_date=end, city=car.city, price_paid=total,
                )
                Payment.objects.create(
                    rental=rental, amount=total, cardholder=f"{renter.first_name} {renter.last_name}",
                    card_brand="Visa", card_last4="4242",
                )
                Notification.objects.create(
                    user=car.owner, rental=rental, is_read=offset < 0,
                    message=f"{renter.first_name} {renter.last_name}-მა დაჯავშნა თქვენი {car.brand} {car.model}: "
                            f"{start:%d.%m} – {end:%d.%m} ({length} დღე, {total} ₾).",
                )
                bookings += 1

        Favorite.objects.create(user=users[0], car=cars[4])
        Favorite.objects.create(user=users[0], car=cars[3])
        Favorite.objects.create(user=users[1], car=cars[0])

        photos = f"{len(real_photos)} real photos" if real_photos else "drawn pictures"
        self.stdout.write(self.style.SUCCESS(
            f"Added {len(users)} users, {len(cars)} cars ({photos}) and {bookings} bookings. "
            f"Log in with {phones[0]} / {PASSWORD}"
        ))
