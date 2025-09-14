from django.http import JsonResponse
from django.shortcuts import render

# Create your views here.
def index(request):
    if request.method == 'GET':
        return JsonResponse({'message' : 'you are in the membership now pay the fees you fool'})
    
