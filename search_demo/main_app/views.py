from django.shortcuts import render, render_to_response


def v_index(request):
    return render_to_response("index.html")
