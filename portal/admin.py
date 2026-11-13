# admin.py — ადმინ-პანელის (/admin/) პარამეტრები.
# აქ ვუთითებთ, რომელი ცხრილები გამოჩნდეს ადმინ-პანელში და როგორ.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Car, Favorite, Notification, Payment, Rental, User



# მომხმარებლები


# @admin.register(User) — User ცხრილს ვამატებთ ადმინ-პანელში.
# BaseUserAdmin არის Django-ს მზა კლასი მომხმარებლებისთვის (პაროლის შეცვლა და ა.შ.).
# ვაფართოებთ მას, რადგან ჩვენთან შესვლა ხდება ტელეფონით და არა username-ით.
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # სიის დალაგება ტელეფონის ნომრის მიხედვით
    ordering = ["phone"]

    # რომელი სვეტები ჩანს მომხმარებლების სიაში
    list_display = ["phone", "first_name", "last_name", "email", "is_staff"]

    # საძიებო ველი: ძებნა ტელეფონით, სახელით, გვარით ან ელ-ფოსტით
    search_fields = ["phone", "first_name", "last_name", "email"]

    # მომხმარებლის რედაქტირების გვერდი დაყოფილია ბლოკებად:
    # (ბლოკის სათაური, {"fields": [ამ ბლოკის ველები]})
    fieldsets = [
        (None, {"fields": ["phone", "password"]}),  # None = ბლოკს სათაური არ აქვს
        ("პირადი ინფორმაცია", {"fields": ["first_name", "last_name", "email"]}),
        # is_staff — შეუძლია ადმინ-პანელში შესვლა; is_superuser — აქვს ყველა უფლება
        ("უფლებები", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("თარიღები", {"fields": ["last_login", "date_joined"]}),
    ]

    # ახალი მომხმარებლის დამატების გვერდის ველები.
    # password1 და password2 — პაროლი და მისი გამეორება (დასადასტურებლად)
    add_fieldsets = [
        (None, {
            "classes": ["wide"],  # ფართო განლაგება
            "fields": ["phone", "first_name", "last_name", "email", "password1", "password2"],
        }),
    ]



# მანქანები


# admin.ModelAdmin — ჩვეულებრივი ცხრილის ადმინ-პარამეტრები
@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    # სვეტები მანქანების სიაში
    list_display = ["brand", "model", "year", "price", "capacity", "city", "owner", "created_at"]

    # ფილტრები მარჯვენა მხარეს: ქალაქი, ტრანსმისია, ადგილების რაოდენობა
    list_filter = ["city", "transmission", "capacity"]

    # ძებნა ბრენდით, მოდელით ან მფლობელის ტელეფონით.
    # owner__phone ნიშნავს: owner (მფლობელი) ცხრილიდან აიღე phone ველი
    search_fields = ["brand", "model", "owner__phone"]




# Inline — ერთი ცხრილის ჩანაწერი ნაჩვენებია მეორის გვერდის შიგნით.
# აქ: გადახდა ჩანს პირდაპირ ჯავშნის გვერდზე (რადგან Rental და Payment
# ერთმანეთთან დაკავშირებულია ერთი-ერთზე, OneToOneField-ით).
class PaymentInline(admin.StackedInline):  # StackedInline — ველები ერთმანეთის ქვეშ
    model = Payment
    can_delete = False  # გადახდის წაშლა ჯავშნის გვერდიდან აკრძალულია
    extra = 0           # ცარიელი "ახალი გადახდის" ფორმა არ გამოჩნდეს


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    # სვეტები ჯავშნების სიაში
    list_display = ["car", "user", "start_date", "end_date", "price_paid", "status", "city"]

    # ფილტრები: სტატუსი (გადახდილი / გაუქმებული) და ქალაქი
    list_filter = ["status", "city"]

    # სიის ზემოთ ჩნდება თარიღების ნავიგაცია: წელი → თვე → დღე
    date_hierarchy = "start_date"

    # ჯავშნის გვერდზე ქვემოთ ჩანს მისი გადახდაც
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # ბარათის მხოლოდ ტიპი და ბოლო 4 ციფრი ინახება — სრული ნომერი არასდროს
    list_display = ["rental", "amount", "card_brand", "card_last4", "status", "created_at"]

    # ფილტრები: სტატუსი (გადახდილი / დაბრუნებული) და ბარათის ტიპი (Visa, Mastercard…)
    list_filter = ["status", "card_brand"]



# მოწონებულები და შეტყობინებები


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    # ვინ რომელი მანქანა მოიწონა და როდის
    list_display = ["user", "car", "created_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    # ვის გაეგზავნა, რა ტექსტით, წაკითხულია თუ არა
    list_display = ["user", "message", "is_read", "created_at"]

    # ფილტრი: წაკითხული / წაუკითხავი
    list_filter = ["is_read"]