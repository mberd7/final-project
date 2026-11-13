"""მისამართები: რომელი მისამართი რომელ view-ს (views.py) ეკუთვნის.

path("მისამართი", view-ფუნქცია, name="სახელი")
  - <int:car_id> — მისამართის ნაწილი, რომელიც რიცხვად გადაეცემა view-ს:
                   /car/5/ -> car_detail(request, car_id=5)
  - name — მისამართის სახელი. შაბლონებში ბმული: {% url 'car_detail' car.id %},
           Python-ში: redirect("car_detail", car_id=5). ასე მისამართის შეცვლისას
           მხოლოდ ეს ფაილი იცვლება.
Django სიას ამოწმებს ზემოდან ქვემოთ და იყენებს პირველ დამთხვევას.
"""
from django.urls import path

from . import views

urlpatterns = [
    # საჯარო გვერდები
    path("", views.home, name="home"),                                   # მთავარი
    path("cars/", views.cars_view, name="cars"),                         # ყველა მანქანა + დალაგება
    path("filter/", views.filter_view, name="filter"),                   # ძებნა
    path("car/<int:car_id>/", views.car_detail, name="car_detail"),      # მანქანის გვერდი

    # დაჯავშნა და გადახდა
    path("car/<int:car_id>/checkout/", views.checkout_view, name="checkout"),
    path("booking/<int:rental_id>/", views.booking_detail, name="booking_detail"),          # ქვითარი
    path("booking/<int:rental_id>/cancel/", views.cancel_booking, name="cancel_booking"),   # გაუქმება

    # მოქმედებები მანქანაზე
    path("car/<int:car_id>/favorite/", views.favorite_view, name="favorite"),     # მოწონება
    path("car/<int:car_id>/delete/", views.delete_car_view, name="delete_car"),   # წაშლა
    path("add-car/", views.add_car_view, name="add_car"),                         # დამატება

    # ანგარიში
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("notifications/", views.notifications_view, name="notifications"),
]