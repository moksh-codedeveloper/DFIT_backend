from django.http import JsonResponse
from django.shortcuts import render

# Create your views here.
def index(request) :
    if request.method == 'GET' :
        return JsonResponse({'message': 'You are in the image analyzer'})

