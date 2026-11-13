"""Views — ფუნქციები, რომლებიც ამუშავებენ გვერდებს.

ყოველი view იღებს request-ს (მოთხოვნას) და აბრუნებს პასუხს:
  - render(request, შაბლონი, {მონაცემები}) — HTML გვერდი
  - redirect("სახელი") — ბრაუზერის გადამისამართება სხვა გვერდზე
რომელი მისამართი რომელ view-ს ეკუთვნის, წერია urls.py-ში.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from .cities import CITIES
from .forms import (
    MAX_BOOKING_DAYS, AddCarForm, BookingForm, FilterForm, LoginForm, PaymentForm, RegisterForm,
)
from .models import Car, Favorite, Notification, Payment, Rental

HOME_POPULAR = 4         # რამდენი პოპულარული მანქანა ჩანს მთავარ გვერდზე
HOME_RANDOM = 8          # რამდენი ახლახან დამატებული მანქანა ჩანს მთავარ გვერდზე
CARS_PER_PAGE = 8        # მანქანების ბადე ერთ გვერდზე (ყველა მანქანა, ძებნა, მოწონებული, განცხადებები)
BOOKINGS_PER_PAGE = 10   # ჯავშნების სია ერთ გვერდზე (პროფილში)

# "ყველა მანქანის" გვერდის დალაგების ვარიანტები:
# გასაღები მისამართში -> (ტექსტი სიაში, ORDER BY — "-" ნიშნავს კლებადობით)
SORTS = {
    "newest": ("ახალი განცხადებები", ["-created_at"]),
    "price_asc": ("ფასი: იაფიდან ძვირისკენ", ["price", "-created_at"]),
    "price_desc": ("ფასი: ძვირიდან იაფისკენ", ["-price", "-created_at"]),
    "year_desc": ("წელი: ახლიდან ძველისკენ", ["-year", "-created_at"]),
    "year_asc": ("წელი: ძველიდან ახლისკენ", ["year", "-created_at"]),
    "popular": ("პოპულარობით", ["-times_rented", "-created_at"]),
}

# სადემონსტრაციო გადახდა: ეს სატესტო ბარათი ყოველთვის "უარყოფილია ბანკის მიერ"
DECLINED_TEST_CARD = "4000000000000002"


# ---------------------------------------------------------------------------
# დამხმარე ფუნქციები
# ---------------------------------------------------------------------------

def _redirect_back(request, fallback, **kwargs):
    """დაბრუნება იმ გვერდზე, საიდანაც მომხმარებელი მოვიდა — მაგრამ მხოლოდ ამავე საიტის ფარგლებში.

    მისამართს ვამოწმებთ, რომ ვინმემ ამ ფორმით მომხმარებელი სხვა (მავნე) საიტზე არ გადაიყვანოს.
    """
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(fallback, **kwargs)


def paginate(request, items, per_page):
    """აბრუნებს items-ის ერთ გვერდს (?page=2 მისამართში). არასწორი ნომრისას ჩანს ბოლო გვერდი."""
    page = Paginator(items, per_page).get_page(request.GET.get("page"))
    # გვერდების ნომრები საჩვენებლად, გამოტოვებულების ნაცვლად "…": 1 2 3 … 9
    page.numbers = list(page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1))
    page.ellipsis = Paginator.ELLIPSIS
    return page


def _notify(user, rental, message):
    """შეტყობინების შექმნა (🔔)."""
    Notification.objects.create(user=user, rental=rental, message=message)


# ---------------------------------------------------------------------------
# საჯარო გვერდები (ყველასთვის ხელმისაწვდომი)
# ---------------------------------------------------------------------------

def home(request):
    """მთავარი გვერდი: პოპულარული და ახლახან დამატებული მანქანები."""
    # პოპულარული = ყველაზე ხშირად დაჯავშნილი. COUNT(...) ითვლის SQLite და არა Python:
    #   annotate — თითოეულ მანქანას უმატებს times_rented-ს (გადახდილი ჯავშნების რაოდენობა)
    #   filter   — ვტოვებთ მხოლოდ ერთხელ მაინც დაჯავშნილებს
    #   order_by — ჯერ ყველაზე ხშირად დაჯავშნილი, თანაბრობისას — უახლესი
    popular = (
        Car.objects.annotate(times_rented=Count("rentals", filter=Q(rentals__status=Rental.PAID)))
        .filter(times_rented__gt=0)
        .order_by("-times_rented", "-created_at")[:HOME_POPULAR]
    )
    # მეორე სექციაში — უახლესი მანქანები, პოპულარულების გარდა (რომ არ განმეორდეს)
    popular_ids = [car.id for car in popular]
    other_cars = Car.objects.exclude(id__in=popular_ids).order_by("-created_at")[:HOME_RANDOM]

    # ლექსიკონის ({...}) ყოველი გასაღები შაბლონში ცვლადად იქცევა, მაგ. {{ car_count }}
    return render(request, "portal/home.html", {
        "popular": popular,
        "other_cars": other_cars,
        "cities": Car.objects.order_by("city").values_list("city", flat=True).distinct(),
        "car_count": Car.objects.count(),
        "today": date.today(),
    })


def cars_view(request):
    """ყველა მანქანა, მომხმარებლის არჩეული დალაგებით, გვერდებად."""
    sort = request.GET.get("sort")
    if sort not in SORTS:
        sort = "newest"  # უცნობი მნიშვნელობისას — ნაგულისხმევი დალაგება
    cars = Car.objects.annotate(
        times_rented=Count("rentals", filter=Q(rentals__status=Rental.PAID))
    ).order_by(*SORTS[sort][1])

    return render(request, "portal/cars.html", {
        "page_obj": paginate(request, cars, CARS_PER_PAGE),
        "sort": sort,
        "sorts": [(key, label) for key, (label, _) in SORTS.items()],
    })


def car_detail(request, car_id):
    """ერთი მანქანის გვერდი. car_id მოდის მისამართიდან"""
    # get_object_or_404 — მანქანა, ან თუ არ არსებობს — 404 გვერდი
    # select_related("owner") — მფლობელსაც იმავე მოთხოვნით იღებს (უფრო სწრაფია)
    car = get_object_or_404(Car.objects.select_related("owner"), pk=car_id)
    # მოწონებული აქვს თუ არა ეს მანქანა შესულ მომხმარებელს 
    is_favorite = (
        request.user.is_authenticated
        and Favorite.objects.filter(user=request.user, car=car).exists()
    )
    # დაკავებული თარიღები კალენდრისთვის (calendar.js მათ გადახაზავს)
    booked = [{"start": s.isoformat(), "end": e.isoformat()} for s, e in car.booked_ranges()]
    return render(request, "portal/car_detail.html", {
        "car": car,
        "is_favorite": is_favorite,
        "is_owner": request.user == car.owner,  # მფლობელი ხედავს "წაშლას" ქირაობის ნაცვლად
        "booked": booked,
        "today": date.today(),
        "max_days": MAX_BOOKING_DAYS,
        # ძებნის გვერდზე არჩეული თარიღები კალენდარში წინასწარ მოინიშნება
        "preselect_start": request.GET.get("start", ""),
        "preselect_end": request.GET.get("end", ""),
    })


def filter_view(request):
    """ძებნის გვერდი: ქალაქი, წლები, ტევადობა და თავისუფალი თარიღები."""
    all_cars = Car.objects.all()

    # ჩამოსაშლელი სიების ვარიანტები მოდის ბაზაში რეალურად არსებული მანქანებიდან
    cities = all_cars.order_by("city").values_list("city", flat=True).distinct()
    years = all_cars.order_by("-year").values_list("year", flat=True).distinct()
    capacities = all_cars.order_by("capacity").values_list("capacity", flat=True).distinct()

    # request.GET or None — თუ ფილტრები არ არის გაგზავნილი, ფორმა ცარიელია
    form = FilterForm(request.GET or None, cities=cities)
    searched = form.is_bound  # დააჭირა თუ არა მომხმარებელმა "ძებნას"
    cars = all_cars.none()
    date_query = ""
    if searched and form.is_valid():
        cars = form.filter(all_cars)
        if form.cleaned_data.get("start_date"):
            # არჩეულ თარიღებს ვაწებებთ მანქანის ბმულს -> კალენდარში წინასწარ მოინიშნება
            date_query = "?" + urlencode({
                "start": form.cleaned_data["start_date"].isoformat(),
                "end": form.cleaned_data["end_date"].isoformat(),
            })

    return render(request, "portal/filter.html", {
        "form": form,
        "page_obj": paginate(request, cars.order_by("-created_at"), CARS_PER_PAGE),
        "searched": searched,
        "values": request.GET,  # რომ ფორმაში არჩეული მნიშვნელობები დარჩეს
        "cities": cities,
        "years": years,
        "capacities": capacities,
        "date_query": date_query,
        "today": date.today(),
    })


# ---------------------------------------------------------------------------
# ანგარიში
# ---------------------------------------------------------------------------
# ფორმის გვერდების ზოგადი სქემა (login_view, register_view, add_car_view):
#   1) GET  (გვერდის გახსნა)        -> ცარიელი ფორმა
#   2) POST (ღილაკზე დაჭერა)         -> ფორმა ამოწმებს მონაცემებს
#      - სწორია  -> ვინახავთ და redirect 
#      - შეცდომა -> იგივე გვერდი წითელი შეცდომებით და შეყვანილი მონაცემებით

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")  # უკვე შესულს შესვლის გვერდი არ სჭირდება

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)  # ასევე აძლევს ვიზიტორს ახალ სესიის ID-ს (უსაფრთხოებისთვის)
        messages.success(request, f"მოგესალმებით, {form.user.first_name}!")
        return _redirect_back(request, "home")

    return render(request, "portal/login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "ანგარიში შეიქმნა. ახლა შეგიძლიათ შესვლა.")
        return redirect("login")

    return render(request, "portal/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


# პროფილის ჩანართები: (გასაღები მისამართში ?tab=..., ტექსტი ღილაკზე)
PROFILE_TABS = [
    ("bookings", "ჩემი ჯავშნები"),
    ("history", "ისტორია"),
    ("favorites", "მოწონებული"),
    ("listings", "ჩემი განცხადებები"),
    ("incoming", "ჩემი მანქანების ჯავშნები"),
]


@login_required
def profile_view(request):
    """პროფილი: სტატისტიკა და 5 ჩანართი, თითოეული გვერდებად."""
    user = request.user
    today = date.today()
    my_rentals = user.rentals.select_related("car", "payment")

    # მიმდინარე და მომავალი ჯავშნები; დასრულებული ან გაუქმებული — "ისტორიაში"
    bookings = my_rentals.filter(status=Rental.PAID, end_date__gte=today).order_by("start_date")
    # Q(...) | Q(...) — "ან": გაუქმებული ან უკვე დასრულებული
    history = my_rentals.filter(Q(status=Rental.CANCELLED) | Q(end_date__lt=today))
    favorites = Car.objects.filter(favorited_by__user=user).order_by("-favorited_by__created_at")
    # ჩემი მანქანები + თითოეულის ჯავშნების რაოდენობა და შემოსავალი
    listings = user.cars.annotate(
        bookings_count=Count("rentals", filter=Q(rentals__status=Rental.PAID)),
        earned=Sum("rentals__price_paid", filter=Q(rentals__status=Rental.PAID)),
    ).order_by("-created_at")  # დათვლისას ნაგულისხმევი დალაგება იკარგება, ამიტომ ხელახლა ვუთითებთ
    # სხვების ჯავშნები ჩემს მანქანებზე (car__owner — მანქანის მფლობელი)
    incoming = Rental.objects.filter(car__owner=user).select_related("car", "user")

    lists = {
        "bookings": bookings, "history": history, "favorites": favorites,
        "listings": listings, "incoming": incoming,
    }
    tab = request.GET.get("tab")
    if tab not in lists:
        tab = "bookings"  # ნაგულისხმევი ჩანართი

    return render(request, "portal/profile.html", {
        "tab": tab,
        "tabs": [(key, label, lists[key].count()) for key, label in PROFILE_TABS],
        "page_obj": paginate(
            request, lists[tab],
            CARS_PER_PAGE if tab in ("favorites", "listings") else BOOKINGS_PER_PAGE,
        ),
        "stats": {
            "trips": my_rentals.filter(status=Rental.PAID).count(),
            # aggregate(Sum) — ჯამს ითვლის ბაზა; "or 0" — თუ ჯავშანი არ არის, ჯამი None-ია
            "spent": my_rentals.filter(status=Rental.PAID).aggregate(t=Sum("price_paid"))["t"] or 0,
            "listings": listings.count(),
            "earned": incoming.filter(status=Rental.PAID).aggregate(t=Sum("price_paid"))["t"] or 0,
        },
    })


@login_required
def notifications_view(request):
    # list(...) — ვიღებთ სიას ახლავე, სანამ წაკითხულად მოვნიშნავთ (რომ ახლები გამოჩნდეს)
    notifications = list(request.user.notifications.select_related("rental__car"))
    # გვერდის გახსნა ყველა შეტყობინებას წაკითხულად ნიშნავს
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "portal/notifications.html", {"notifications": notifications})


# ---------------------------------------------------------------------------
# დაჯავშნა: კალენდარი -> გადახდა -> დადასტურება
# ---------------------------------------------------------------------------

@login_required
def checkout_view(request, car_id):
    """გადახდის გვერდი. GET — თარიღების შემოწმება და ფორმის ჩვენება; POST — გადახდა."""
    car = get_object_or_404(Car.objects.select_related("owner"), pk=car_id)
    if car.owner_id == request.user.id:
        messages.error(request, "საკუთარი მანქანის დაჯავშნა შეუძლებელია.")
        return redirect("car_detail", car_id=car.id)

    # თარიღები პირველად მოდის კალენდრიდან (GET), შემდეგ — ფორმის დამალული ველებიდან (POST)
    booking = BookingForm(request.POST if request.method == "POST" else request.GET, car=car)
    if not booking.is_valid():
        for error in booking.non_field_errors() or [e for errs in booking.errors.values() for e in errs]:
            messages.error(request, error)
        return redirect("car_detail", car_id=car.id)

    payment = PaymentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and payment.is_valid():
        if payment.cleaned_data["card_number"] == DECLINED_TEST_CARD:
            payment.add_error(None, "ბანკმა გადახდა უარყო. სცადეთ სხვა ბარათი.")
        else:
            rental = _create_booking(request.user, car, booking, payment)
            if rental is None:
                messages.error(request, "სანამ იხდიდით, ეს თარიღები სხვამ დაჯავშნა. აირჩიეთ სხვა დღეები.")
                return redirect("car_detail", car_id=car.id)
            messages.success(request, "გადახდა წარმატებულია! ჯავშანი დადასტურებულია.")
            return redirect("booking_detail", rental_id=rental.id)

    return render(request, "portal/checkout.html", {
        "car": car,
        "booking": booking,
        "form": payment,
        "start": booking.cleaned_data["start_date"],
        "end": booking.cleaned_data["end_date"],
        "days": booking.days,
        "total": booking.total,
    })


def _create_booking(user, car, booking, payment):
    """ინახავს ჯავშანს + გადახდას + შეტყობინებას ერთად. აბრუნებს None-ს, თუ თარიღები დაიკავეს.

    transaction.atomic() — "ყველაფერი ან არაფერი": თუ რომელიმე ნაბიჯი ჩავარდება,
    არცერთი ჩანაწერი არ შეინახება (არ იქნება ჯავშანი გადახდის გარეშე).
    """
    start, end = booking.cleaned_data["start_date"], booking.cleaned_data["end_date"]
    with transaction.atomic():
        # ტრანზაქციის შიგნით კიდევ ერთხელ ვამოწმებთ: იქნებ ამასობაში სხვამ დაჯავშნა
        if not car.is_available(start, end):
            return None
        rental = Rental.objects.create(
            user=user, car=car, start_date=start, end_date=end,
            city=car.city, price_paid=booking.total,
        )
        Payment.objects.create(
            rental=rental, amount=booking.total,
            cardholder=payment.cleaned_data["cardholder"].strip(),
            card_brand=payment.brand, card_last4=payment.last4,  # არასდროს სრული ნომერი
        )
        _notify(car.owner, rental, (
            f"{user.first_name} {user.last_name}-მა დაჯავშნა თქვენი {car.brand} {car.model}: "
            f"{start:%d.%m} – {end:%d.%m} ({rental.days} დღე, {rental.price_paid} ₾)."
        ))
    return rental


@login_required
def booking_detail(request, rental_id):
    """ჯავშნის ქვითარი."""
    rental = get_object_or_404(
        Rental.objects.select_related("car", "car__owner", "user", "payment"), pk=rental_id
    )
    # ჯავშანს ხედავს მხოლოდ მქირავებელი და მანქანის მფლობელი — სხვისთვის 404
    if request.user not in (rental.user, rental.car.owner):
        raise Http404
    return render(request, "portal/booking.html", {"rental": rental})


@require_POST
@login_required
def cancel_booking(request, rental_id):
    """ჯავშნის გაუქმება (მხოლოდ საკუთარი და მხოლოდ დაწყებამდე)."""
    # user=request.user — სხვისი ჯავშანი ვერ მოიძებნება -> 404
    rental = get_object_or_404(Rental.objects.select_related("car"), pk=rental_id, user=request.user)
    if not rental.can_cancel:
        messages.error(request, "დაწყებული ან დასრულებული ჯავშნის გაუქმება შეუძლებელია.")
        return redirect("booking_detail", rental_id=rental.id)

    # არაფერი იშლება — იცვლება სტატუსები, ისტორია რჩება
    with transaction.atomic():
        rental.status = Rental.CANCELLED
        rental.save(update_fields=["status"])
        Payment.objects.filter(rental=rental).update(status=Payment.REFUNDED)
        _notify(rental.car.owner, rental, (
            f"{request.user.first_name} {request.user.last_name}-მა გააუქმა ჯავშანი: "
            f"{rental.car.brand} {rental.car.model}, {rental.start_date:%d.%m} – {rental.end_date:%d.%m}."
        ))
    messages.info(request, f"ჯავშანი გაუქმდა. {rental.price_paid} ₾ დაგიბრუნდებათ ბარათზე.")
    return redirect(reverse("profile") + "?tab=history")


@require_POST
@login_required
def favorite_view(request, car_id):
    """ერთი დაჭერა — მოწონება, მეორე — მოწონების გაუქმება."""
    car = get_object_or_404(Car, pk=car_id)
    # get_or_create — პოულობს ჩანაწერს, ან ქმნის ახალს; created=True თუ ახალი შეიქმნა
    favorite, created = Favorite.objects.get_or_create(user=request.user, car=car)
    if created:
        messages.success(request, "დაემატა მოწონებულებში.")
    else:
        favorite.delete()
        messages.info(request, "წაიშალა მოწონებულებიდან.")
    return _redirect_back(request, "car_detail", car_id=car.id)


# ---------------------------------------------------------------------------
# ჩემი განცხადებები
# ---------------------------------------------------------------------------

@login_required
def add_car_view(request):
    """მანქანის დამატება. request.FILES — ატვირთული ფოტოები."""
    form = AddCarForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        car = form.save(commit=False)  # commit=False — ჯერ არ ვინახავთ, ჯერ მფლობელი უნდა მივუთითოთ
        car.owner = request.user  # მფლობელი (და ტელეფონი) მოდის შესვლიდან და არა ფორმიდან
        car.save()
        messages.success(request, "მანქანა წარმატებით დაემატა!")
        return redirect("car_detail", car_id=car.id)

    return render(request, "portal/add_car.html", {"form": form, "cities_count": len(CITIES)})


@require_POST
@login_required
def delete_car_view(request, car_id):
    """განცხადების წაშლა — მხოლოდ მფლობელს და მხოლოდ თუ მომავალი ჯავშნები არ აქვს."""
    car = get_object_or_404(Car, pk=car_id, owner=request.user)  # სხვისი მანქანა -> 404
    if car.rentals.filter(status=Rental.PAID, end_date__gte=date.today()).exists():
        messages.error(request, "მანქანას აქვს მომავალი ჯავშნები — წაშლა ახლა შეუძლებელია.")
        return redirect("car_detail", car_id=car.id)
    car.delete()
    messages.info(request, "განცხადება წაიშალა.")
    return redirect(reverse("profile") + "?tab=listings")