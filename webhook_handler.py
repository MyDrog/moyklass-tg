from moyklass_client import get_user, get_payment, get_lesson, get_class, get_course
import templates


def handle_payment_new(webhook: dict) -> dict:
    obj = webhook["object"]
    user = get_user(obj["userId"])
    payment = get_payment(obj["paymentId"])

    text = templates.PAYMENT_NEW.format(
        user_name=user["name"],
        summa=payment["summa"],
        date=payment["date"],
    )

    return {
        "text": text,
        "phone": user.get("phone")
    }


def handle_lesson_debt(webhook: dict) -> dict:
    obj = webhook["object"]
    user = get_user(obj["userId"])

    # Получаем данные занятия
    lesson = get_lesson(obj["lessonId"])
    lesson_date = "-".join(reversed(lesson["date"].split("-")))  # формат DD-MM-YYYY
    lesson_date_time = f"{lesson_date} {lesson['endTime']}"

    # Получаем данные группы
    class_info = get_class(lesson["classId"])
    class_name = class_info.get("name", "")
    course_id = class_info.get("courseId")

    # Получаем данные курса
    course_info = get_course(course_id) if course_id else {}
    course_name = f"{course_info.get('name', '')} {class_name}"

    text = templates.LESSON_DEBT.format(
        course=course_name,
        lesson_date=lesson_date_time
    )

    return {
        "text": text,
        "phone": user.get("phone")
    }


def process_webhook(webhook: dict) -> dict | None:
    event = webhook.get("event")
    obj = webhook.get("object", {})

    if not obj:
        return None

    if event == "payment_new":
        return handle_payment_new(webhook)
    elif event == "sub_lesson_in_debt":
        return handle_lesson_debt(webhook)

    return None
