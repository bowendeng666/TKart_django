from store.models import Variation
from orders.models import Order, OrderProduct
from django.contrib import messages
from django.http import request
from django.http.response import HttpResponse
from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from carts.views import _cart_id
from carts.models import Cart, CartItem
import requests

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            phone_number = form.cleaned_data['phone_number']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = email.split('@')[0]

            user = Account.objects.create_user(first_name=first_name, last_name=last_name,
                                               email=email, username=username, password=password)
            user.phone_number = phone_number
            user.save()

            #create corresponding user profile
            profile = UserProfile()
            profile.user_id = user.id
            profile.profile_picture = 'default/default-user.png'
            profile.save()
            # user activation
            current_site = get_current_site(request)
            mail_subject = 'Action required to activate your account.'
            message = render_to_string('accounts/account_verification_email.html', {
                'user': user,
                'domain': current_site,
                # encode user's id
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[
                                      to_email, ], from_email='developer.bowen@qq.com')
            send_email.send()
            return redirect('/accounts/login/?command=verification&email=' + email)
            # messages.success(request, 'Please check your mailbox and activate your account.')
    else:
        form = RegistrationForm()
    context = {
        'form': form,
    }
    return render(request, 'accounts/register.html', context)


def login(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        user = auth.authenticate(email=email, password=password)
        #check if the user account have any item in cart
        if user:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                is_cart_item_exists = CartItem.objects.filter(cart=cart).exists()
                if is_cart_item_exists:
                    cart_items = CartItem.objects.filter(cart=cart)
                    
                    product_variation = []
                    #grabing the product variations by cart id
                    for item in cart_items:
                        variations = item.variations.all()
                        product_variation.append(list(variations))
                    
                    #get cart items from the user to access his product variations
                    cart_items = CartItem.objects.filter(user=user)
                    existing_variation_list = []
                    item_ids = []
                    for item in cart_items:
                        existing_variation = item.variations.all()
                        existing_variation_list.append(list(existing_variation))
                        item_ids.append(item.id)

                    #find common variation
                    for ele in product_variation:
                        if ele in existing_variation_list:
                            index = existing_variation_list.index(ele)
                            item_id = item_ids[index]
                            item = CartItem.objects.get(id=item_id)
                            item.quantity += 1
                            item.user = user
                            item.save()
                        else:
                            cart_items = CartItem.objects.filter(cart=cart)
                            for item in cart_items:
                                item.user = user
                                item.save()
            except:
                pass
            auth.login(request, user)
            messages.success(request, 'Login success.')
            # Get the departure url
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query # return the 'next' statement
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage)
                
            except:
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
            return redirect('login')
    return render(request, 'accounts/login.html')


@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'Logout success.')
    return redirect('login')


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(
            request, 'Congratulation! Your account is now activated.')
        return redirect('login')
    else:
        messages.error(request, 'Invalid activation link')
        return redirect('register')


@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.order_by('-created_time').filter(user_id=request.user.id, is_ordered=True)
    orders_count = orders.count()
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    profile_picture = user_profile.profile_picture.url
    context = {
        'orders_count': orders_count,
        'profile_picture': profile_picture,
    }
    return render(request, 'accounts/dashboard.html', context)


def forgotPassword(request):
    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)

            # Reset password email
            current_site = get_current_site(request)
            mail_subject = 'Reset Your Password.'
            message = render_to_string('accounts/reset_password_email.html', {
                'user': user,
                'domain': current_site,
                # encode user's id
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[
                                      to_email, ], from_email='developer.bowen@qq.com')
            send_email.send()

            messages.success(
                request, 'Password reset email has been sent to your email address.')
            return redirect('login')
        else:
            messages.error(request, 'Account does not exist!')
            return redirect('forgotPassword')
    return render(request, 'accounts/forgotPassword.html')


def resetpassword_validate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    if user and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Plesae reset your password.')
        return redirect('resetPassword')
    else:
        messages.error(request, 'This link is expired')
        return redirect('login')



def resetPassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            uid = request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, 'Reset Password Success.')
            return redirect('login')
        else:
            messages.error(request, 'Password do not match!')
            return redirect('resetPassword')
    else:
        return render(request, 'accounts/resetPassword.html')


@login_required(login_url='login')
def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_time')
    context = {
        'orders': orders,
    }
    return render(request,'accounts/my_orders.html', context)

@login_required(login_url='login')
def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        #update the existing user profile
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'User Profile successfully updated.')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=request.user) #store existing data
        profile_form = UserProfileForm(instance=userprofile)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile,
    }
    return render(request, 'accounts/edit_profile.html', context)


@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_pasword = request.POST['new_password']
        confirm_password = request.POST['confirm_new_password']

        user = Account.objects.get(username__exact=request.user.username)

        if new_pasword == confirm_password:
            password_match = user.check_password(current_password)
            if password_match:
                user.set_password(new_pasword)
                user.save()
                messages.success(request, 'Password is successfully updated.')
                return redirect('change_password')
            else:
                messages.error(request, 'Password entered is not valid.')
                return redirect('change_password')
        else:
            messages.error(request, 'Password does not match.')
            return redirect('change_password')
    return render(request, 'accounts/change_password.html')


@login_required(login_url='login')
def order_detail(request, order_id):
    order_detail = OrderProduct.objects.filter(order__order_number=order_id)
    order = Order.objects.get(order_number=order_id)
    sub_total = 0
    for item in order_detail:
        sub_total += item.product_price * item.quantity

    context = {
        'order_detail': order_detail,
        'order': order,
        'sub_total': sub_total,
        'tax': '%.2f' % order.tax,
        'grand_total': '%.2f' % order.order_total
    }
    return render(request,'accounts/order_detail.html', context)