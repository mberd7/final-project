"""მონაცემთა ბაზის (SQLite) ცხრილები.

Django ქვემოთ მოცემულ თითოეულ კლასს აქცევს ცხრილად db.sqlite3 ფაილში:
    User          -> portal_user          (დარეგისტრირებული მომხმარებლები, შესვლა ტელეფონით)
    Car           -> portal_car           (განცხადებები, 3 ფოტოთი)
    Rental        -> portal_rental        (ჯავშანი: რომელი მანქანა, რომელი თარიღიდან რომლამდე)
    Payment       -> portal_payment       (ჯავშნის გადახდა; ბარათის სრული ნომერი არასდროს ინახება)
    Favorite      -> portal_favorite      (მოწონებული მანქანები)
    Notification  -> portal_notification  (შეტყობინება მფლობელს, როცა მის მანქანას დაჯავშნიან)
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import date

from django.db import models
from django.db.models import F, Q

from .cities import CITIES

# შეზღუდვები, რომლებსაც ფორმებიც იყენებს (forms.py)
MIN_YEAR = 1950   # ყველაზე ძველი დასაშვები გამოშვების წელი
MIN_SEATS = 1     # მინიმალური ადგილების რაოდენობა
MAX_SEATS = 9     # მაქსიმალური ადგილების რაოდენობა

# ტრანსმისიის ვარიანტები: (ბაზაში შენახული მნიშვნელობა, მომხმარებლისთვის ნაჩვენები ტექსტი)
TRANSMISSIONS = [
    ("automatic", "ავტომატიკა"),
    ("manual", "მექანიკა"),
    ("tiptronic", "ტიპტრონიკი"),
]


# მომხმარებლები

class UserManager(BaseUserManager):
    """ქმნის მომხმარებლებს, რომლებიც შედიან ტელეფონის ნომრით (username-ის ნაცვლად).

    Django-ს ჩვეულებრივი მენეჯერი ელოდება username-ს, ჩვენ კი ის ამოვიღეთ,
    ამიტომ საკუთარი მენეჯერი გვჭირდება. მას იყენებს მაგ. `createsuperuser` ბრძანება.
    """

    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("ტელეფონის ნომერი სავალდებულოა")
        extra["email"] = self.normalize_email(extra.get("email", ""))
        user = self.model(phone=phone, **extra)
        user.set_password(password)  # ინახება პაროლის ჰეში (დაშიფრული სახე) და არა თავად პაროლი
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        # სუპერმომხმარებელს აქვს ადმინ-პანელში შესვლის და ყველა მოქმედების უფლება
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra)


class User(AbstractUser):
    """მომხმარებელი. AbstractUser-იდან ვიღებთ მზა ველებს (პაროლი, უფლებები, თარიღები)."""

    username = None  # username ამოღებულია — მის ნაცვლად ტელეფონის ნომერია
    phone = models.CharField("ტელეფონის ნომერი", max_length=20, unique=True)  # unique — ორ მომხმარებელს ერთი ნომერი ვერ ექნება
    first_name = models.CharField("სახელი", max_length=50)
    last_name = models.CharField("გვარი", max_length=50)
    email = models.EmailField("ელ-ფოსტა", unique=True)

    USERNAME_FIELD = "phone"   # შესვლისას ამ ველს ვამოწმებთ
    REQUIRED_FIELDS = ["first_name", "last_name", "email"]  # createsuperuser ამ ველებსაც მოითხოვს

    objects = UserManager()

    def __str__(self):
        # როგორ გამოჩნდეს მომხმარებელი ტექსტად (მაგ. ადმინ-პანელში)
        return f"{self.first_name} {self.last_name} ({self.phone})"


# ---------------------------------------------------------------------------
# მანქანები
# ---------------------------------------------------------------------------

class Car(models.Model):
    """მანქანის განცხადება."""

    # ForeignKey — "ეკუთვნის": ყოველ მანქანას ჰყავს ერთი მფლობელი (User).
    # ერთ მომხმარებელს შეიძლება ჰქონდეს ბევრი მანქანა (ერთი-ბევრთან კავშირი).
    # on_delete=CASCADE — მომხმარებლის წაშლისას იშლება მისი მანქანებიც.
    # related_name="cars" — მომხმარებლის მანქანების მიღება: user.cars.all()
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="cars", verbose_name="მფლობელი"
    )
    brand = models.CharField("ბრენდი", max_length=50)
    model = models.CharField("მოდელი", max_length=50)
    year = models.PositiveIntegerField("გამოშვების წელი", validators=[MinValueValidator(MIN_YEAR)])
    price = models.PositiveIntegerField("ფასი დღეში (₾)", validators=[MinValueValidator(1)])
    capacity = models.PositiveSmallIntegerField(
        "ტევადობა", validators=[MinValueValidator(MIN_SEATS), MaxValueValidator(MAX_SEATS)]
    )
    transmission = models.CharField("ტრანსმისია", max_length=20, choices=TRANSMISSIONS)
    city = models.CharField("ქალაქი", max_length=50, choices=[(c, c) for c in CITIES])
    fuel_capacity = models.PositiveSmallIntegerField("ბაკის მოცულობა (ლ)")
    # ფოტოები ინახება media/cars/ საქაღალდეში, ბაზაში კი — მხოლოდ ფაილის მისამართი
    image1 = models.FileField("ფოტო 1", upload_to="cars/")
    image2 = models.FileField("ფოტო 2", upload_to="cars/")
    image3 = models.FileField("ფოტო 3", upload_to="cars/")
    # არასავალდებულო: ავსებს ბრაუზერი (GPS), მომხმარებელი ხელით არ წერს.
    # null=True — ბაზაში შეიძლება იყოს ცარიელი; blank=True — ფორმაში არ არის სავალდებულო
    latitude = models.FloatField("განედი", null=True, blank=True)
    longitude = models.FloatField("გრძედი", null=True, blank=True)
    created_at = models.DateTimeField("დამატების დრო", auto_now_add=True)  # ივსება ავტომატურად შექმნისას

    class Meta:
        ordering = ["-created_at"]  # ნაგულისხმევი დალაგება: ჯერ უახლესი ("-" = კლებადობით)
        verbose_name = "მანქანა"
        verbose_name_plural = "მანქანები"

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"

  
    @property
    def photos(self):
        """სამივე ფოტო სიად (ცარიელების გარეშე) — მანქანის გვერდის გალერეისთვის."""
        return [img for img in (self.image1, self.image2, self.image3) if img]

    @property
    def has_location(self):
        """აქვს თუ არა მანქანას კოორდინატები (რუკის საჩვენებლად)."""
        return self.latitude is not None and self.longitude is not None

    def booked_ranges(self):
        """დღეიდან მოყოლებული გადახდილი ჯავშნები (დასაწყისი, დასასრული) წყვილებად — კალენდრისთვის."""
        return list(
            self.rentals.filter(status=Rental.PAID, end_date__gte=date.today())
            .order_by("start_date")
            .values_list("start_date", "end_date")
        )

    def is_available(self, start, end):
        """თავისუფალია თუ არა მანქანა start-დან end-მდე: არცერთი ჯავშანი არ ემთხვევა."""
        return not Rental.overlapping(self, start, end).exists()

    @property
    def map_embed_url(self):
        """OpenStreetMap-ის რუკის მისამართი მანქანის ნიშნულით ."""
        lat, lng, d = self.latitude, self.longitude, 0.01  # d — რუკის ზომა მანქანის გარშემო
        return (
            "https://www.openstreetmap.org/export/embed.html"
            f"?bbox={lng - d},{lat - d},{lng + d},{lat + d}&layer=mapnik&marker={lat},{lng}"
        )


# ---------------------------------------------------------------------------
# ჯავშნები და გადახდები
# ---------------------------------------------------------------------------

class Rental(models.Model):
    """ჯავშანი. ორივე თარიღი ითვლება: 12.05 -> 14.05 არის 3 დღე."""

    # სტატუსის შესაძლო მნიშვნელობები
    PAID = "paid"             # გადახდილი (აქტიური ჯავშანი)
    CANCELLED = "cancelled"   # გაუქმებული (თარიღები ისევ თავისუფალია)
    STATUSES = [(PAID, "გადახდილი"), (CANCELLED, "გაუქმებული")]

    # Rental აკავშირებს ორ ცხრილს: ვინ (User) და რომელი მანქანა (Car)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="rentals", verbose_name="მქირავებელი"
    )
    car = models.ForeignKey(
        Car, on_delete=models.CASCADE, related_name="rentals", verbose_name="მანქანა"
    )
    start_date = models.DateField("აყვანის თარიღი")
    end_date = models.DateField("დაბრუნების თარიღი")
    # ეს ორი ველი კოპირდება დაჯავშნის მომენტში — თუ მფლობელი მოგვიანებით
    # ფასს ან ქალაქს შეცვლის, ძველი ჯავშნის ისტორია არ შეიცვლება
    city = models.CharField("ქალაქი", max_length=50)
    price_paid = models.PositiveIntegerField("გადახდილი თანხა (₾)")
    status = models.CharField("სტატუსი", max_length=20, choices=STATUSES, default=PAID)
    created_at = models.DateTimeField("შექმნის დრო", auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "ჯავშანი"
        verbose_name_plural = "ჯავშნები"
        constraints = [
            # თავად ბაზა არ მიიღებს ჯავშანს, რომელის დასასრული დაწყებამდეა
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")), name="rental_end_after_start"
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.car} ({self.start_date} – {self.end_date})"

    @staticmethod
    def overlapping(car, start, end):
        """მანქანის გადახდილი ჯავშნები, რომლებსაც start..end-თან ერთი დღე მაინც აქვთ საერთო.

        ორმაგი დაჯავშნის წესი: ორი ჯავშანი ემთხვევა, თუ
            არსებულის დასაწყისი <= ახლის დასასრული   და
            არსებულის დასასრული >= ახლის დასაწყისი
        start_date__lte ნიშნავს "<=" , end_date__gte ნიშნავს ">=".
        გაუქმებული ჯავშნები არ ითვლება (status=PAID).
        """
        return Rental.objects.filter(
            car=car, status=Rental.PAID, start_date__lte=end, end_date__gte=start
        )

    @property
    def days(self):
        """დღეების რაოდენობა (ორივე დღე ითვლება, ამიტომ +1)."""
        return (self.end_date - self.start_date).days + 1

    @property
    def code(self):
        """ჯავშნის მოკლე ნომერი მომხმარებლისთვის, მაგ. GZA-000042."""
        return f"GZA-{self.pk:06d}"

    @property
    def state(self):
        """'cancelled', 'upcoming', 'active' ან 'finished' — ფერადი იარლიყისთვის.

        გამოითვლება დღევანდელი თარიღით: გაუქმებული / მომავალი / მიმდინარე / დასრულებული.
        """
        if self.status == self.CANCELLED:
            return "cancelled"
        today = date.today()
        if self.start_date > today:
            return "upcoming"
        if self.end_date >= today:
            return "active"
        return "finished"

    @property
    def can_cancel(self):
        """გაუქმება შეიძლება მხოლოდ ჯერ არდაწყებული ჯავშნის."""
        return self.state == "upcoming"


class Payment(models.Model):
    """სადემონსტრაციო გადახდა. ინახება მხოლოდ ბარათის ბოლო 4 ციფრი —
    ბარათის სრული ნომერი და CVC არასდროს ინახება."""

    PAID = "paid"           # გადახდილი
    REFUNDED = "refunded"   # დაბრუნებული (ჯავშნის გაუქმებისას)
    STATUSES = [(PAID, "გადახდილი"), (REFUNDED, "დაბრუნებული")]

    # OneToOneField — ერთი-ერთთან კავშირი: ერთ ჯავშანს აქვს ზუსტად ერთი გადახდა.
    # ეს არის ForeignKey + unique წესი (rental_id ცხრილში ორჯერ ვერ შეგხვდება).
    # related_name="payment" — ჯავშნიდან გადახდის მიღება: rental.payment
    rental = models.OneToOneField(Rental, on_delete=models.CASCADE, related_name="payment")
    amount = models.PositiveIntegerField("თანხა (₾)")
    cardholder = models.CharField("ბარათის მფლობელი", max_length=100)
    card_brand = models.CharField("ბარათის ტიპი", max_length=20)   # მაგ. Visa, Mastercard
    card_last4 = models.CharField("ბოლო 4 ციფრი", max_length=4)
    status = models.CharField("სტატუსი", max_length=20, choices=STATUSES, default=PAID)
    created_at = models.DateTimeField("გადახდის დრო", auto_now_add=True)

    class Meta:
        verbose_name = "გადახდა"
        verbose_name_plural = "გადახდები"

    def __str__(self):
        return f"{self.amount} ₾ · {self.card_brand} •••• {self.card_last4}"


# ---------------------------------------------------------------------------
# მოწონებულები და შეტყობინებები
# ---------------------------------------------------------------------------

class Favorite(models.Model):
    """მოწონებული მანქანა.(ბევრი-ბევრთან კავშირი): ერთ მომხმარებელს შეუძლია ბევრი მანქანის მოწონება,
    ერთ მანქანას კი — ბევრი მომხმარებლისგან."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "მოწონებული"
        verbose_name_plural = "მოწონებულები"
        constraints = [
            # ერთ მომხმარებელს ერთი და იგივე მანქანის მოწონება მხოლოდ ერთხელ შეუძლია
            models.UniqueConstraint(fields=["user", "car"], name="unique_favorite"),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.car}"


class Notification(models.Model):
    """შეტყობინება მომხმარებლისთვის (🔔 ღილაკი მენიუში).
    მაგ.: "გიორგიმ დაჯავშნა თქვენი Toyota Prius" — იგზავნება მანქანის მფლობელთან."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", verbose_name="მიმღები"
    )
    # რომელ ჯავშანს ეხება (არასავალდებულო: null=True)
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField("შეტყობინება", max_length=255)
    is_read = models.BooleanField("წაკითხულია", default=False)  # წაუკითხავები ჩანს 🔔-ზე რიცხვად
    created_at = models.DateTimeField("დრო", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "შეტყობინება"
        verbose_name_plural = "შეტყობინებები"

    def __str__(self):
        return self.message