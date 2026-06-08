import sqlalchemy as sa
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from models import db, Course, Category, User, Review
from tools import CoursesFilter, ImageSaver

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

REVIEW_SORTS = {
    'new': 'Сначала новые',
    'positive': 'Сначала положительные',
    'negative': 'Сначала отрицательные',
}

RATING_LABELS = {
    5: 'отлично',
    4: 'хорошо',
    3: 'удовлетворительно',
    2: 'неудовлетворительно',
    1: 'плохо',
    0: 'ужасно',
}

def params():
    return { p: request.form.get(p) or None for p in COURSE_PARAMS }

def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }


def get_review_sort():
    sort = request.args.get('sort', 'new')
    if sort not in REVIEW_SORTS:
        return 'new'
    return sort


def reviews_query(course_id, sort='new'):
    q = db.select(Review).filter_by(course_id=course_id)
    if sort == 'positive':
        q = q.order_by(Review.rating.desc(), Review.created_at.desc())
    elif sort == 'negative':
        q = q.order_by(Review.rating.asc(), Review.created_at.desc())
    else:
        q = q.order_by(Review.created_at.desc())
    return q


def recalculate_course_rating(course):
    # Для себя: рейтинг считаем по фактическим отзывам, чтобы не было рассинхрона.
    stats = db.session.execute(
        db.select(
            sa.func.coalesce(sa.func.sum(Review.rating), 0),
            sa.func.count(Review.id),
        ).filter(Review.course_id == course.id)
    ).one()
    course.rating_sum = int(stats[0] or 0)
    course.rating_num = int(stats[1] or 0)

@bp.route('/')
def index():
    courses = CoursesFilter(**search_params()).perform()
    pagination = db.paginate(courses)
    courses = pagination.items
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())

@bp.route('/new')
@login_required
def new():
    course = Course()
    categories = db.session.execute(db.select(Category)).scalars()
    users = db.session.execute(db.select(User)).scalars()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users,
                           course=course)

@bp.route('/create', methods=['POST'])
@login_required
def create():
    f = request.files.get('background_img')
    img = None
    course = Course()
    try:
        if f and f.filename:
            img = ImageSaver(f).save()

        image_id = img.id if img else None
        course = Course(**params(), background_image_id=image_id)
        db.session.add(course)
        db.session.commit()
    except IntegrityError as err:
        flash(f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})', 'danger')
        db.session.rollback()
        categories = db.session.execute(db.select(Category)).scalars()
        users = db.session.execute(db.select(User)).scalars()
        return render_template('courses/new.html',
                            categories=categories,
                            users=users,
                            course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))

@bp.route('/<int:course_id>')
def show(course_id):
    course = db.get_or_404(Course, course_id)
    latest_reviews = db.session.execute(
        db.select(Review)
        .filter_by(course_id=course_id)
        .order_by(Review.created_at.desc())
        .limit(5)
    ).scalars().all()
    user_review = None
    if current_user.is_authenticated:
        user_review = db.session.execute(
            db.select(Review)
            .filter_by(course_id=course_id, user_id=current_user.id)
        ).scalar()

    return render_template(
        'courses/show.html',
        course=course,
        latest_reviews=latest_reviews,
        user_review=user_review,
        rating_labels=RATING_LABELS,
    )


@bp.route('/<int:course_id>/reviews')
def reviews(course_id):
    course = db.get_or_404(Course, course_id)
    sort = get_review_sort()
    pagination = db.paginate(reviews_query(course_id, sort), per_page=5)
    user_review = None
    if current_user.is_authenticated:
        user_review = db.session.execute(
            db.select(Review)
            .filter_by(course_id=course_id, user_id=current_user.id)
        ).scalar()

    return render_template(
        'courses/reviews.html',
        course=course,
        reviews=pagination.items,
        pagination=pagination,
        sort=sort,
        sort_options=REVIEW_SORTS,
        user_review=user_review,
        rating_labels=RATING_LABELS,
    )


@bp.route('/<int:course_id>/reviews/create', methods=['POST'])
@login_required
def create_review(course_id):
    course = db.get_or_404(Course, course_id)
    existing_review = db.session.execute(
        db.select(Review)
        .filter_by(course_id=course_id, user_id=current_user.id)
    ).scalar()
    if existing_review:
        flash('Вы уже оставили отзыв к этому курсу.', 'warning')
        return redirect(request.form.get('next') or url_for('courses.show', course_id=course_id))

    rating_raw = request.form.get('rating')
    text = (request.form.get('text') or '').strip()

    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = -1

    if rating not in RATING_LABELS:
        flash('Некорректная оценка в форме отзыва.', 'danger')
        return redirect(request.form.get('next') or url_for('courses.show', course_id=course_id))
    if not text:
        flash('Текст отзыва не может быть пустым.', 'danger')
        return redirect(request.form.get('next') or url_for('courses.show', course_id=course_id))

    try:
        review = Review(rating=rating, text=text, course_id=course.id, user_id=current_user.id)
        db.session.add(review)
        recalculate_course_rating(course)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('Не удалось сохранить отзыв. Возможно, вы уже оставили отзыв к этому курсу.', 'danger')
        return redirect(request.form.get('next') or url_for('courses.show', course_id=course_id))

    flash('Спасибо! Ваш отзыв успешно добавлен.', 'success')
    return redirect(request.form.get('next') or url_for('courses.show', course_id=course_id))
