from flask import Flask, render_template, send_from_directory
from flask_migrate import Migrate
from sqlalchemy.exc import SQLAlchemyError
from models import db, Category, Image
from auth import bp as auth_bp, init_login_manager
from courses import bp as courses_bp

app = Flask(__name__)
application = app

app.config.from_pyfile('config.py')

db.init_app(app)
migrate = Migrate(app, db)

init_login_manager(app)

@app.errorhandler(SQLAlchemyError)
def handle_sqlalchemy_error(err):
    error_msg = ('Возникла ошибка при подключении к базе данных. '
                 'Повторите попытку позже.')
    return f'{error_msg} (Подробнее: {err})', 500

app.register_blueprint(auth_bp)
app.register_blueprint(courses_bp)

@app.route('/')
def index():
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template(
        'index.html',
        categories=categories,
    )

@app.route('/images/<image_id>')
def image(image_id):
    img = db.get_or_404(Image, image_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               img.storage_filename)

from models import db, Category, User  # если еще не импортировано

def seed_initial_data():
    if not db.session.execute(db.select(Category)).first():
        db.session.add_all([
            Category(name='Программирование', parent_id=None),
            Category(name='Математика', parent_id=None),
            Category(name='Языкознание', parent_id=None),
        ])

    u1 = db.session.execute(db.select(User).filter_by(login='user')).scalar()
    if not u1:
        u1 = User(first_name='Иван', last_name='Иванов', login='user')
        u1.set_password('qwerty')
        db.session.add(u1)

    u2 = db.session.execute(db.select(User).filter_by(login='user2')).scalar()
    if not u2:
        u2 = User(first_name='Петр', last_name='Петров', login='user2')
        u2.set_password('qwerty')
        db.session.add(u2)

    db.session.commit()

with app.app_context():
    db.create_all()
    seed_initial_data()
if __name__ == '__main__':
    app.run(debug=True)
