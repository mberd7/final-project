"""ფორმები — მომხმარებლის მიერ შეყვანილი მონაცემების შემოწმება.

ფორმის მუშაობის პრინციპი:
  - form.is_valid() უშვებს ყველა შემოწმებას
  - clean_ველი() — ამოწმებს ერთ კონკრეტულ ველს (მაგ. clean_phone)
  - clean() — ამოწმებს რამდენიმე ველს ერთად (მაგ. დაწყების და დასრულების თარიღს)
  - შეცდომისას ValidationError — ტექსტი წითლად გამოჩნდება ფორმაში
  - წარმატებისას გასუფთავებული მონაცემები არის form.cleaned_data-ში
"""
import re
from datetime import date, timedelta

from django import forms
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError

from .cities import CITIES
from .models import MAX_SEATS, MIN_SEATS, MIN_YEAR, Car, Rental, User

MAX_BOOKING_DAYS = 60     # ერთი ჯავშნის მაქსიმალური ხანგრძლივობა (დღე)
BOOK_AHEAD_DAYS = 365     # რამდენი დღით ადრე შეიძლება დაჯავშნა

# თარიღები იწერება დღე.თვე.წელი
DATE_FORMATS = ["%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"]
DATE_ERROR = "თარიღი ჩაწერეთ ასე: 25.12.26"

# ფოტოების შემოწმების პარამეტრები
MAX_PHOTO_MB = 5
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"   # ყოველი PNG ფაილი ამ ბაიტებით იწყება
JPEG_SIGNATURE = b"\xff\xd8\xff"       # ყოველი JPEG ფაილი ამ ბაიტებით იწყება
PHOTO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
PHONE_RE = re.compile(r"^\+?\d{9,15}$")  # არასავალდებულო "+" და 9-15 ციფრი

REQUIRED = "ეს ველი სავალდებულოა."


def normalize_phone(raw):
    """'591 29-98-99' -> '591299899'. ერთი და იგივე წესი რეგისტრაციისთვის და შესვლისთვის."""
    return re.sub(r"[\s\-()]", "", raw or "")  # შლის ცარიელ ადგილებს, ტირეებს და ფრჩხილებს


def validate_photo(photo):
    """იღებს მხოლოდ ნამდვილ PNG/JPG/JPEG/WEBP სურათებს, მაქსიმუმ MAX_PHOTO_MB ზომის."""
    if not photo.name.lower().endswith(PHOTO_EXTENSIONS):
        raise ValidationError("დაშვებულია მხოლოდ PNG, JPG, JPEG ან WEBP ფორმატი.")
    if photo.size > MAX_PHOTO_MB * 1024 * 1024:
        raise ValidationError(f"ფოტო არ უნდა აღემატებოდეს {MAX_PHOTO_MB} MB-ს.")
    # ფაილს შეიძლება გადაარქვან სახელი .jpg-ად ისე, რომ სურათი არ იყოს,
    # ამიტომ ვამოწმებთ ფაილის პირველ ბაიტებს ("ხელმოწერას")
    start = photo.read(12)
    photo.seek(0)  # ვბრუნდებით ფაილის დასაწყისში, რომ შემდეგ მთლიანად შეინახოს
    is_webp = start[:4] == b"RIFF" and start[8:12] == b"WEBP"
    if not (start.startswith(PNG_SIGNATURE) or start.startswith(JPEG_SIGNATURE) or is_webp):
        raise ValidationError("ეს ფაილი არ არის სურათი.")


class GeorgianErrorsMixin:
    """ყველა ველს ანიჭებს ერთნაირ ქართულ შეტყობინებას "ეს ველი სავალდებულოა".

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages["required"] = REQUIRED


# ---------------------------------------------------------------------------
# ანგარიში: რეგისტრაცია და შესვლა
# ---------------------------------------------------------------------------

class RegisterForm(GeorgianErrorsMixin, forms.ModelForm):
    """რეგისტრაციის ფორმა (5 ველი). ModelForm — ფორმა, რომელიც აგებულია მოდელზე (User)."""

    # პაროლი მოდელის ველებში ცალკე არ არის, ამიტომ აქ ვამატებთ
    password = forms.CharField(
        label="პაროლი",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "email"]
        # სათაურები განზრახ ცალკე წერია: წინააღმდეგ შემთხვევაში Django
        # მოდელის სახელის პირველ ასოს გაადიდებს და ქართული მთავრულად გადაიქცევა
        labels = {
            "first_name": "სახელი",
            "last_name": "გვარი",
            "phone": "ტელეფონის ნომერი",
            "email": "ელ-ფოსტა",
        }
        # autocomplete ეხმარება ბრაუზერს ველების ავტომატურ შევსებაში
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "591299899"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        error_messages = {
            "phone": {"unique": "ამ ნომრით მომხმარებელი უკვე არსებობს."},
            "email": {"unique": "ამ ელ-ფოსტით მომხმარებელი უკვე არსებობს.",
                      "invalid": "შეიყვანეთ სწორი ელ-ფოსტა."},
        }

    def clean_phone(self):
        """ნომრის გასუფთავება და შემოწმება: სწორი ფორმატი და ჯერ არ არის დაკავებული."""
        phone = normalize_phone(self.cleaned_data["phone"])
        if not PHONE_RE.match(phone):
            raise ValidationError("შეიყვანეთ სწორი ტელეფონის ნომერი (მაგ: 591299899).")
        if User.objects.filter(phone=phone).exists():
            raise ValidationError("ამ ნომრით მომხმარებელი უკვე არსებობს.")
        return phone

    def clean_email(self):
        # ელ-ფოსტა ინახება პატარა ასოებით, რომ Nino@x.ge და nino@x.ge ერთი იყოს
        return self.cleaned_data["email"].strip().lower()

    def _post_clean(self):
        super()._post_clean()
        # Django-ს პაროლის წესები: სიგრძე, ზედმეტად მარტივი, მხოლოდ ციფრები და ა.შ.
        password = self.cleaned_data.get("password")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])  # ინახება ჰეში და არა პაროლი
        if commit:
            user.save()
        return user


class LoginForm(GeorgianErrorsMixin, forms.Form):
    """შესვლის ფორმა (2 ველი): ტელეფონი და პაროლი."""

    phone = forms.CharField(
        label="ტელეფონის ნომერი",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "autofocus": True}),
    )
    password = forms.CharField(
        label="პაროლი",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None  # წარმატებული შემოწმების შემდეგ აქ იქნება ნაპოვნი მომხმარებელი
        super().__init__(*args, **kwargs)

    def clean(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        password = self.cleaned_data.get("password")
        if phone and password:
            # authenticate ამოწმებს, არსებობს თუ არა ასეთი მომხმარებელი ამ პაროლით
            self.user = authenticate(self.request, phone=phone, password=password)
            if self.user is None:
                raise ValidationError("ტელეფონის ნომერი ან პაროლი არასწორია.")
        return self.cleaned_data


# ---------------------------------------------------------------------------
# მანქანები
# ---------------------------------------------------------------------------

class AddCarForm(GeorgianErrorsMixin, forms.ModelForm):
    """მანქანის დამატების ფორმა. მფლობელი (და მისი ტელეფონი) ფორმაში არ არის —
    ის view-ში ემატება შესული მომხმარებლიდან."""

    class Meta:
        model = Car
        fields = [
            "brand", "model", "year", "price", "capacity", "transmission",
            "city", "fuel_capacity", "image1", "image2", "image3",
            "latitude", "longitude",
        ]
        labels = {
            "brand": "მანქანის ბრენდი",
            "model": "მანქანის მოდელი",
            "year": "გამოშვების წელი",
            "transmission": "მანქანის ტრანსმისია",
            "city": "ქალაქი",
            "image1": "ფოტო 1",
            "image2": "ფოტო 2",
            "image3": "ფოტო 3",
            "price": "გაქირავების ფასი დღეში (₾)",
            "capacity": "მანქანის ტევადობა (ადგილი)",
            "fuel_capacity": "ბენზინის ბაკის მოცულობა (ლ)",
        }
        widgets = {
            "brand": forms.TextInput(attrs={"placeholder": "Mercedes"}),
            "model": forms.TextInput(attrs={"placeholder": "E320"}),
            "year": forms.NumberInput(attrs={"placeholder": "2015"}),
            "price": forms.NumberInput(attrs={"placeholder": "90"}),
            "capacity": forms.NumberInput(attrs={"placeholder": "4"}),
            "fuel_capacity": forms.NumberInput(attrs={"placeholder": "60"}),
            # accept — ფაილის არჩევისას ბრაუზერი აჩვენებს მხოლოდ ამ ტიპის ფაილებს
            "image1": forms.FileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp"}),
            "image2": forms.FileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp"}),
            "image3": forms.FileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp"}),
            # ავსებს JavaScript მოწყობილობის GPS-იდან — მომხმარებელი მათ არ წერს
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ჩამოსაშლელი სიების პირველი ვარიანტი: "აირჩიეთ ..."
        self.fields["transmission"].choices = [("", "აირჩიეთ ტრანსმისია")] + list(
            self.fields["transmission"].choices
        )[1:]
        self.fields["city"].choices = [("", "აირჩიეთ ქალაქი")] + [(c, c) for c in CITIES]
        # სამივე ფოტოს ვამოწმებთ validate_photo ფუნქციით
        for name in ("image1", "image2", "image3"):
            self.fields[name].validators.append(validate_photo)
        for name in ("year", "price", "capacity", "fuel_capacity"):
            self.fields[name].error_messages["invalid"] = "შეიყვანეთ მთელი რიცხვი."

    def _check_range(self, name, low, high):
        """დამხმარე: ამოწმებს, რომ რიცხვი low-სა და high-ს შორისაა."""
        value = self.cleaned_data[name]
        if not low <= value <= high:
            raise ValidationError(f"მნიშვნელობა უნდა იყოს {low}-დან {high}-მდე.")
        return value

    def clean_year(self):
        return self._check_range("year", MIN_YEAR, date.today().year + 1)

    def clean_price(self):
        return self._check_range("price", 1, 100000)

    def clean_capacity(self):
        return self._check_range("capacity", MIN_SEATS, MAX_SEATS)

    def clean_fuel_capacity(self):
        return self._check_range("fuel_capacity", 1, 200)

    def clean(self):
        data = super().clean()
        lat, lng = data.get("latitude"), data.get("longitude")
        # შეუძლებელ კოორდინატებს უბრალოდ ვაიგნორებთ, მთელ ფორმას არ ვაფუჭებთ
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            data["latitude"] = data["longitude"] = None
        return data


# ---------------------------------------------------------------------------
# დაჯავშნა და გადახდა
# ---------------------------------------------------------------------------

class BookingForm(forms.Form):
    """აყვანის და დაბრუნების თარიღები. ამოწმებს, რომ მანქანა ყველა დღეს თავისუფალია."""

    start_date = forms.DateField(label="აყვანა", input_formats=DATE_FORMATS)
    end_date = forms.DateField(label="დაბრუნება", input_formats=DATE_FORMATS)

    def __init__(self, *args, car, **kwargs):
        self.car = car  # რომელ მანქანას ვჯავშნით — საჭიროა თავისუფლების შესამოწმებლად
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages["required"] = "აირჩიეთ აყვანის და დაბრუნების თარიღები."
            field.error_messages["invalid"] = DATE_ERROR

    def clean(self):
        """ჯავშნის ყველა წესი თანმიმდევრობით. პირველივე დარღვევა აჩერებს შემოწმებას."""
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if not start or not end:
            return data

        today = date.today()
        if start < today:
            raise ValidationError("წარსული თარიღის დაჯავშნა შეუძლებელია.")
        if end < start:
            raise ValidationError("დაბრუნების თარიღი აყვანის თარიღზე ადრე ვერ იქნება.")
        if start > today + timedelta(days=BOOK_AHEAD_DAYS):
            raise ValidationError("დაჯავშნა შესაძლებელია მაქსიმუმ ერთი წლით ადრე.")
        if (end - start).days + 1 > MAX_BOOKING_DAYS:
            raise ValidationError(f"ერთი ჯავშანი მაქსიმუმ {MAX_BOOKING_DAYS} დღეა.")
        # ორმაგი დაჯავშნის შემოწმება (წესი აღწერილია Rental.overlapping-ში, models.py)
        if not self.car.is_available(start, end):
            raise ValidationError("მანქანა ამ თარიღებში უკვე დაჯავშნილია. აირჩიეთ სხვა დღეები.")
        return data

    @property
    def days(self):
        """დღეების რაოდენობა (ორივე დღე ითვლება)."""
        return (self.cleaned_data["end_date"] - self.cleaned_data["start_date"]).days + 1

    @property
    def total(self):
        """გადასახდელი თანხა: დღეები × დღიური ფასი."""
        return self.days * self.car.price


def luhn_ok(number):
    """Luhn-ის საკონტროლო ჯამი — მას აკმაყოფილებს ყველა ნამდვილი ბარათის ნომერი.

    მარჯვნიდან ყოველ მეორე ციფრს ვაორმაგებთ (თუ 9-ზე მეტი გამოვა, ვაკლებთ 9-ს),
    ყველაფერს ვკრებთ — ჯამი უნდა იყოფოდეს 10-ზე. ასე იჭერს შეცდომით აკრეფილ ციფრს.
    """
    total = 0
    for i, digit in enumerate(reversed(number)):
        n = int(digit)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def card_brand(number):
    """ბარათის ტიპი პირველი ციფრებით: 4 — Visa, 51-55 ან 2221-2720 — Mastercard, 34/37 — Amex."""
    if number.startswith("4"):
        return "Visa"
    if number[:2] in {"51", "52", "53", "54", "55"} or 2221 <= int(number[:4]) <= 2720:
        return "Mastercard"
    if number[:2] in {"34", "37"}:
        return "Amex"
    return "ბარათი"


class PaymentForm(GeorgianErrorsMixin, forms.Form):
    """სადემონსტრაციო გადახდის ფორმა: ამოწმებს, რომ ბარათი ნამდვილს ჰგავს, მაგრამ თანხა არ ჩამოიჭრება.

    ბარათის სრული ნომერი და CVC გამოიყენება მხოლოდ შესამოწმებლად და არასდროს ინახება.
    """

    cardholder = forms.CharField(
        label="ბარათის მფლობელი", max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "cc-name", "placeholder": "NINO BERIDZE"}),
    )
    card_number = forms.CharField(
        label="ბარათის ნომერი", max_length=23,
        widget=forms.TextInput(attrs={
            "autocomplete": "cc-number", "inputmode": "numeric",
            "placeholder": "4242 4242 4242 4242",
        }),
    )
    expiry = forms.CharField(
        label="მოქმედების ვადა", max_length=5,
        widget=forms.TextInput(attrs={"autocomplete": "cc-exp", "inputmode": "numeric", "placeholder": "MM/YY"}),
    )
    cvc = forms.CharField(
        label="CVC", max_length=4,
        # PasswordInput — აკრეფისას CVC წერტილებით ჩანს
        widget=forms.PasswordInput(attrs={"autocomplete": "cc-csc", "inputmode": "numeric", "placeholder": "•••"}),
    )

    def clean_card_number(self):
        """ვშლით ჰარებს/ტირეებს; უნდა იყოს 13-19 ციფრი და გაიაროს Luhn-ის შემოწმება."""
        number = re.sub(r"[\s-]", "", self.cleaned_data["card_number"])
        if not number.isdigit() or not 13 <= len(number) <= 19 or not luhn_ok(number):
            raise ValidationError("ბარათის ნომერი არასწორია.")
        return number

    def clean_expiry(self):
        """ფორმატი MM/YY, თვე 1-12 და ვადა არ უნდა იყოს გასული."""
        match = re.fullmatch(r"\s*(\d{1,2})\s*/\s*(\d{2})\s*", self.cleaned_data["expiry"])
        if not match or not 1 <= int(match[1]) <= 12:
            raise ValidationError("მიუთითეთ ვადა ფორმატით MM/YY.")
        month, year = int(match[1]), 2000 + int(match[2])
        today = date.today()
        if (year, month) < (today.year, today.month):
            raise ValidationError("ბარათს ვადა გაუვიდა.")
        return f"{month:02d}/{year % 100:02d}"

    def clean_cvc(self):
        cvc = self.cleaned_data["cvc"].strip()
        if not re.fullmatch(r"\d{3,4}", cvc):
            raise ValidationError("CVC უნდა იყოს 3 ან 4 ციფრი.")
        return cvc

    @property
    def brand(self):
        return card_brand(self.cleaned_data["card_number"])

    @property
    def last4(self):
        """ბარათის ბოლო 4 ციფრი — მხოლოდ ეს ინახება ბაზაში."""
        return self.cleaned_data["card_number"][-4:]


# ---------------------------------------------------------------------------
# ძებნა (ფილტრაცია)
# ---------------------------------------------------------------------------

class FilterForm(forms.Form):
    """ყველა ველი არასავალდებულოა — ფილტრები მუშაობს ცალ-ცალკეც და ერთადაც."""

    city = forms.ChoiceField(label="ქალაქი", required=False)
    start_year = forms.IntegerField(label="წელი (დან)", required=False)
    end_year = forms.IntegerField(label="წელი (მდე)", required=False)
    capacity = forms.IntegerField(label="ტევადობა", required=False)
    start_date = forms.DateField(label="აყვანა", required=False, input_formats=DATE_FORMATS)
    end_date = forms.DateField(label="დაბრუნება", required=False, input_formats=DATE_FORMATS)

    def __init__(self, *args, cities=(), **kwargs):
        super().__init__(*args, **kwargs)
        # ქალაქების სია მოდის view-დან — მხოლოდ ის ქალაქები, სადაც მანქანები რეალურად არის
        self.fields["city"].choices = [("", "ნებისმიერი")] + [(c, c) for c in cities]
        self.fields["start_date"].error_messages["invalid"] = DATE_ERROR
        self.fields["end_date"].error_messages["invalid"] = DATE_ERROR

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and not end:
            data["end_date"] = end = start          # მხოლოდ ერთი თარიღი = ერთი დღე
        elif end and not start:
            data["start_date"] = start = end
        if start and end and end < start:
            raise ValidationError("დაბრუნების თარიღი აყვანის თარიღზე ადრე ვერ იქნება.")
        return data

    def filter(self, cars):
        """იყენებს მხოლოდ შევსებულ ფილტრებს. ყოველი .filter() ემატება SQL-ში როგორც "AND"."""
        data = self.cleaned_data
        if data.get("city"):
            cars = cars.filter(city=data["city"])
        if data.get("start_year"):
            cars = cars.filter(year__gte=data["start_year"])    # წელი >= დან
        if data.get("end_year"):
            cars = cars.filter(year__lte=data["end_year"])      # წელი <= მდე
        if data.get("capacity"):
            cars = cars.filter(capacity=data["capacity"])
        if data.get("start_date"):
            # ვტოვებთ გარეთ ყველა მანქანას, რომელსაც აქვს გადახდილი ჯავშანი,
            # არჩეულ თარიღებთან ერთი დღე მაინც საერთო (იგივე წესი, რაც overlapping-ში)
            busy = Rental.objects.filter(
                status=Rental.PAID,
                start_date__lte=data["end_date"],
                end_date__gte=data["start_date"],
            ).values("car_id")
            cars = cars.exclude(id__in=busy)
        return cars