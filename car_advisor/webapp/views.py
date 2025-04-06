from io import BytesIO
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, CarDataForm
from .models import Request, AnalyzedReviews
from django.http import HttpResponse
from .component_keys import component_keys_ru_to_en
import matplotlib.pyplot as plt
from django.db import models
import json # для работы с JSON

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('personal_account')
    else:
        form = CustomUserCreationForm()
    return render(request, 'webapp/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('personal_account')
    else:
        form = AuthenticationForm()
    return render(request, 'webapp/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def personal_account_view(request):
    user_requests = Request.objects.filter(user=request.user).order_by('-request_datetime')

    return render(request, 'webapp/personal_account.html', {'user_requests': user_requests})


from django.shortcuts import get_object_or_404


@login_required
def view_request_details(request, request_id):
    request_obj = get_object_or_404(Request, id=request_id, user=request.user)

    return render(request, 'webapp/request_details.html', {'request': request_obj})


@login_required
def edit_profile_view(request):
    # TODO: Реализовать редактирование профиля пользователя (email, возможно пароль)
    return HttpResponse("Редактирование профиля в разработке")

def home_view(request):
    return render(request, 'webapp/home.html')


@login_required
def car_data_input_view(request):
    if request.method == 'POST':
        form = CarDataForm(request.POST)
        if form.is_valid():
            car_brand = form.cleaned_data['car_brand']
            car_model = form.cleaned_data['car_model']
            search_criteria = form.cleaned_data['search_criteria']

            component_ratings_data = calculate_component_ratings(car_model)

            # Получаем топ объявлений
            top_ads_data = generate_top_ads(car_model, search_criteria) or []

            # Сохранение запроса в историю
            request_obj = Request.objects.create(
                user=request.user,
                car_brand=car_brand,
                car_model=car_model,
                search_criteria=search_criteria,
                component_ratings_data=component_ratings_data,
                top_ads_data=top_ads_data
            )


            return render(request, 'webapp/result.html', {
                'car_brand': car_brand,
                'car_model': car_model,
                'component_ratings_data': component_ratings_data,
                'top_ads_data': top_ads_data,
                'request_id': request_obj.id
            })
    else:
        form = CarDataForm()
    return render(request, 'webapp/car_data_input.html', {'form': form})

def calculate_component_ratings(car_model):

    reviews = AnalyzedReviews.objects.filter(model__iexact=car_model)

    if not reviews.exists():
        return None

    grouped_ratings = {}

    for category_name, category_data in component_keys_ru_to_en.items():
        en_category_key = category_data["en_key"]
        ru_synonyms = category_data["ru_keys"]
        category_ratings = [] # list for rating of categories

        for review in reviews:
            review_analysis_json = review.analysis

            if isinstance(review_analysis_json, dict):
                for ru_component_key in ru_synonyms:
                    rating_value = review_analysis_json.get(ru_component_key)

                    if rating_value is not None:
                        try:
                            rating = float(rating_value)
                            category_ratings.append(rating)
                        except ValueError:
                            print(f"Не удалось преобразовать оценку в число для компонента '{ru_component_key}' (категория '{category_name}') в отзыве: {review.summary}")
            else:
                print(f"Ожидался JSON-словарь в поле analysis, но получен: {type(review_analysis_json)}. Отзыв: {review.summary}")

        if category_ratings:
            average_rating = sum(category_ratings) / len(category_ratings) # average rating of each synonyms
            grouped_ratings[category_name] = round(average_rating, 1) # average rating of each categories
        else:
            grouped_ratings[category_name] = None

    return grouped_ratings # list for categories

def generate_top_ads(car_model, search_criteria):
    # TODO: Реализовать логику формирования топа объявлений + генерацию qr
    pass

@login_required
def generate_squares(request):
    # last request by user
    last_request = Request.objects.filter(user=request.user).order_by('-request_datetime').first()

    if not last_request or not last_request.component_ratings_data:
        return HttpResponse("Нет данных для отображения", content_type="text/plain")

    data = last_request.component_ratings_data

    # delete None-value
    filtered_data = {key: value for key, value in data.items() if value is not None}

    if not filtered_data:
        return HttpResponse("Нет данных для отображения", content_type="text/plain")

    criteria = list(filtered_data.keys())
    values = list(filtered_data.values())

    colors = plt.cm.get_cmap("tab20", len(criteria))
    markers = ['o', 's', '^', 'D', 'x', '+', 'v', '<', '>', 'p'] * 2

    # Make axes
    plt.figure(figsize=(10, 8))

    for i, (criterion, value) in enumerate(zip(criteria, values)):
        plt.scatter(value, i, color=colors(i), label=criterion, marker=markers[i % len(markers)])

    plt.title("Оценки различных критериев")
    plt.xlabel("Оценка")
    plt.ylabel("Критерии")

    plt.legend(loc="best", fontsize=8, bbox_to_anchor=(1.05, 1))

    # save png to buffer
    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)

    # response png to user
    return HttpResponse(buffer, content_type="image/png")






