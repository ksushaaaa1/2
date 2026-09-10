from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'neon-beat-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///neonbeat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
login_manager.login_message_category = 'info'


# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    track_name = db.Column(db.String(200), nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tempo = db.Column(db.Integer)
    mood = db.Column(db.String(100))
    reference_track = db.Column(db.String(200))
    status = db.Column(db.String(50), default='pending')  # pending, in_progress, completed, cancelled
    admin_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Создание админа при первом запуске
def create_admin():
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@neonbeat.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Администратор создан: admin / admin123")


# Главная страница (публичная)
@app.route('/')
def index():
    return render_template('index.html')


# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        # Проверка существования пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован', 'error')
            return redirect(url_for('register'))

        # Создание пользователя
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Регистрация успешна! Добро пожаловать в NEON BEAT', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Вход выполнен успешно!', 'success')

            if user.is_admin:
                return redirect(url_for('admin_panel'))
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный email или пароль', 'error')

    return render_template('login.html')


# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# Личный кабинет (дашборд)
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_panel'))
    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('dashboard.html', orders=user_orders)


# Создание заказа на бит
@app.route('/create_order', methods=['POST'])
@login_required
def create_order():
    track_name = request.form.get('track_name')
    genre = request.form.get('genre')
    description = request.form.get('description')
    tempo = request.form.get('tempo')
    mood = request.form.get('mood')
    reference_track = request.form.get('reference_track')

    order = Order(
        user_id=current_user.id,
        track_name=track_name,
        genre=genre,
        description=description,
        tempo=tempo,
        mood=mood,
        reference_track=reference_track
    )

    db.session.add(order)
    db.session.commit()

    flash('Заявка на создание бита успешно отправлена!', 'success')
    return redirect(url_for('dashboard'))


# Отмена заказа
@app.route('/cancel_order/<int:order_id>')
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id == current_user.id and order.status == 'pending':
        order.status = 'cancelled'
        db.session.commit()
        flash('Заказ отменен', 'info')
    return redirect(url_for('dashboard'))


# Админ-панель
@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))

    orders = Order.query.order_by(Order.created_at.desc()).all()
    users = User.query.filter_by(is_admin=False).all()

    stats = {
        'total_users': User.query.filter_by(is_admin=False).count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status='pending').count(),
        'completed_orders': Order.query.filter_by(status='completed').count()
    }

    return render_template('admin.html', orders=orders, users=users, stats=stats)


# Обновление статуса заказа (админ)
@app.route('/update_order_status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    admin_comment = request.form.get('admin_comment', '')

    order.status = new_status
    order.admin_comment = admin_comment
    order.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Статус заказа обновлен на: {new_status}', 'success')
    return redirect(url_for('admin_panel'))


# API для получения статистики (для админа)
@app.route('/api/stats')
@login_required
def api_stats():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    return jsonify({
        'total_users': User.query.filter_by(is_admin=False).count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status='pending').count(),
        'completed_orders': Order.query.filter_by(status='completed').count()
    })


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(debug=True, port=5000)