from moyklass_client import get_user, get_payment, get_lesson, get_subscription
import templates


def handle_payment_new(webhook: dict) -> str:
    obj = webhook["object"]
    user = get_user(obj["userId"])
    payment = get_payment(obj["paymentId"])

    # user["name"] содержит полное имя
    return templates.PAYMENT_NEW.format(
        user_name=user["name"],
        summa=payment["summa"],
        date=payment["date"],
    )


def handle_lesson_absent(webhook: dict) -> str:
    obj = webhook["object"]
    user = get_user(obj["userId"])
    lesson = get_lesson(obj["lessonId"])
    return templates.LESSON_ABSENT.format(
        user_name=f'{user["lastName"]} {user["firstName"]}',
        lesson_date=lesson["date"],
    )


def handle_lesson_debt(webhook: dict) -> str:
    obj = webhook["object"]
    user = get_user(obj["userId"])
    lesson = get_lesson(obj["lessonId"])
    return templates.LESSON_DEBT.format(
        user_name=f'{user["lastName"]} {user["firstName"]}',
        lesson_date=lesson["date"],
    )


def handle_subscription_expired(webhook: dict) -> str:
    obj = webhook["object"]
    user = get_user(obj["userId"])
    subscription = get_subscription(obj["subscriptionId"])
    return templates.SUBSCRIPTION_EXPIRED.format(
        user_name=f'{user["lastName"]} {user["firstName"]}',
        end_date=subscription["endDate"],
    )


def process_webhook(webhook: dict) -> str | None:
    event = webhook.get("event")
    if event == "payment_new":
        return handle_payment_new(webhook)
    elif event == "lesson_absent":
        return handle_lesson_absent(webhook)
    elif event == "lesson_debt":
        return handle_lesson_debt(webhook)
    elif event == "subscription_expired":
        return handle_subscription_expired(webhook)
    return None
