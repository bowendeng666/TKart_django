from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from carts.models import CartItem
from .models import Order, Payment, OrderProduct
from store.models import Product
from .forms import OrderForm
import datetime, json
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
# Create your views here.

def place_order(request, total=0, quantity=0):
    current_user = request.user

    #if the there is not cart item, then redirect to store page
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')
    
    grand_total, tax = 0,0
    #calculate grand_total and tax
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2*total)/100
    grand_total = total + tax
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            #Store billing information to Order table
            newOrder = Order()
            newOrder.user = current_user
            newOrder.first_name = form.cleaned_data['first_name']
            newOrder.last_name = form.cleaned_data['last_name']
            newOrder.phone = form.cleaned_data['phone']
            newOrder.email = form.cleaned_data['email']
            newOrder.address_line_1 = form.cleaned_data['address_line_1']
            newOrder.address_line_2 = form.cleaned_data['address_line_2']
            newOrder.country = form.cleaned_data['country']
            newOrder.state = form.cleaned_data['state']
            newOrder.city = form.cleaned_data['city']
            newOrder.order_note = form.cleaned_data['order_note']
            newOrder.order_total = grand_total
            newOrder.tax =  tax
            newOrder.ip = request.META.get('REMOTE_ADDR')#get ip address
            newOrder.save()
            #generate order number,using datetime
            current_date = datetime.date.today().strftime('%Y%m%d')
            order_number = current_date + str(newOrder.id)
            newOrder.order_number = order_number
            newOrder.save()

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number )
            context = {
                'order':order,
                'cart_items':cart_items,
                'total':'%.2f' % total,
                'tax': '%.2f' % tax,
                'grand_total':'%.2f' % grand_total,

            }
            return render(request, 'orders/payments.html', context)
    else:
        return redirect('checkout')

def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])
    #Store transaction info to database
    payment = Payment(
        user = request.user,
        payment_id = body['transID'],
        payment_method = body['payment_method'],
        amount_paid = order.order_total,
        status = body['status'],
    )
    payment.save()
    order.payment = payment
    order.is_ordered = True
    order.save()

    #move cart item to order product
    cart_items = CartItem.objects.filter(user=request.user)
    for item in cart_items:
        orderProduct = OrderProduct()
        orderProduct.order_id = order.id
        orderProduct.payment = payment
        orderProduct.user_id = request.user.id
        orderProduct.product_id = item.product_id
        orderProduct.quantity = item.quantity
        orderProduct.product_price = item.product.price
        orderProduct.ordered = True
        orderProduct.save()

        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderProduct = OrderProduct.objects.get(id=orderProduct.id)
        orderProduct.variations.set(product_variation)
        orderProduct.save()

    #Reduce teh quantity of sold products
        product = Product.objects.get(id=item.product_id)
        product.stock -= item.quantity
        product.save()
    #clear cart
    CartItem.objects.filter(user=request.user).delete()
    #send order email to customer
    mail_subject = '[TKART] We received your order, Thank you!'
    message = render_to_string('orders/order_received_email.html', {
        'user': request.user,
        'order': order
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[
                                to_email, ], from_email='developer.bowen@qq.com')
    send_email.send()

    #send order_num and transID back to payment template to show 'Tnank you' Page
    data = {
        'order_number': order.order_number,
        'transID': payment.payment_id,
    }

    return JsonResponse(data)


def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)
        payment = Payment.objects.get(payment_id=order.payment)


        context = {
            'order': order,
            'ordered_products': ordered_products,
            'payment': payment,
            'sub_total': '%.2f' % (order.order_total - order.tax),
            'tax': '%.2f' % order.tax,
            'grand_total': '%.2f' % order.order_total,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')
    