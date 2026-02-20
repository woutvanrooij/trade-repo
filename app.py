import os
import csv
import io
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, g, Response
)
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'voetbalclub-secret-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voetbalclub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

db = SQLAlchemy(app)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    shifts = db.relationship('Shift', backref='event', cascade='all, delete-orphan', order_by='Shift.start_time')

    @property
    def total_spots(self):
        return sum(t.max_volunteers for s in self.shifts for t in s.tasks)

    @property
    def taken_spots(self):
        return sum(len(t.registrations) for s in self.shifts for t in s.tasks)


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)  # HH:MM
    end_time = db.Column(db.String(5), nullable=False)    # HH:MM
    tasks = db.relationship('Task', backref='shift', cascade='all, delete-orphan')


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    max_volunteers = db.Column(db.Integer, nullable=False, default=1)
    registrations = db.relationship('Registration', backref='task', cascade='all, delete-orphan')

    @property
    def spots_left(self):
        return self.max_volunteers - len(self.registrations)

    @property
    def is_full(self):
        return self.spots_left <= 0


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    volunteer_name = db.Column(db.String(200), nullable=False)
    volunteer_email = db.Column(db.String(200), nullable=False)
    volunteer_phone = db.Column(db.String(50))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    events = Event.query.order_by(Event.date.asc()).all()
    return render_template('index.html', events=events, now=datetime.utcnow().date())


@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_detail.html', event=event)


@app.route('/register/<int:task_id>', methods=['GET', 'POST'])
def register(task_id):
    task = Task.query.get_or_404(task_id)
    if task.is_full:
        flash('Deze taak is al vol.', 'warning')
        return redirect(url_for('event_detail', event_id=task.shift.event_id))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if not name or not email:
            flash('Naam en e-mailadres zijn verplicht.', 'danger')
        else:
            # Prevent double registration for same task
            existing = Registration.query.filter_by(task_id=task_id, volunteer_email=email).first()
            if existing:
                flash('Je bent al aangemeld voor deze taak.', 'warning')
            else:
                reg = Registration(
                    task_id=task_id,
                    volunteer_name=name,
                    volunteer_email=email,
                    volunteer_phone=phone,
                )
                db.session.add(reg)
                db.session.commit()
                flash(f'Je aanmelding voor "{task.name}" is bevestigd!', 'success')
                return redirect(url_for('event_detail', event_id=task.shift.event_id))

    return render_template('register.html', task=task)


@app.route('/cancel/<int:registration_id>', methods=['POST'])
def cancel_registration(registration_id):
    reg = Registration.query.get_or_404(registration_id)
    event_id = reg.task.shift.event_id
    db.session.delete(reg)
    db.session.commit()
    flash('Aanmelding geannuleerd.', 'info')
    return redirect(url_for('event_detail', event_id=event_id))


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Ongeldig wachtwoord.', 'danger')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    events = Event.query.order_by(Event.date.asc()).all()
    return render_template('admin/dashboard.html', events=events)


# --- Events ---

@app.route('/admin/events/new', methods=['GET', 'POST'])
@login_required
def admin_new_event():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        date_str = request.form.get('date', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()

        if not name or not date_str:
            flash('Naam en datum zijn verplicht.', 'danger')
        else:
            event = Event(
                name=name,
                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                location=location,
                description=description,
            )
            db.session.add(event)
            db.session.commit()
            flash('Organisatie aangemaakt.', 'success')
            return redirect(url_for('admin_event_detail', event_id=event.id))

    return render_template('admin/event_form.html', event=None)


@app.route('/admin/events/<int:event_id>')
@login_required
def admin_event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('admin/event_detail.html', event=event)


@app.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        event.name = request.form.get('name', '').strip()
        date_str = request.form.get('date', '').strip()
        event.location = request.form.get('location', '').strip()
        event.description = request.form.get('description', '').strip()
        if not event.name or not date_str:
            flash('Naam en datum zijn verplicht.', 'danger')
        else:
            event.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            db.session.commit()
            flash('Organisatie bijgewerkt.', 'success')
            return redirect(url_for('admin_event_detail', event_id=event.id))
    return render_template('admin/event_form.html', event=event)


@app.route('/admin/events/<int:event_id>/delete', methods=['POST'])
@login_required
def admin_delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Organisatie verwijderd.', 'info')
    return redirect(url_for('admin_dashboard'))


# --- Shifts ---

@app.route('/admin/events/<int:event_id>/shifts/new', methods=['GET', 'POST'])
@login_required
def admin_new_shift(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        if not name or not start_time or not end_time:
            flash('Alle velden zijn verplicht.', 'danger')
        else:
            shift = Shift(event_id=event_id, name=name, start_time=start_time, end_time=end_time)
            db.session.add(shift)
            db.session.commit()
            flash('Dienst toegevoegd.', 'success')
            return redirect(url_for('admin_event_detail', event_id=event_id))
    return render_template('admin/shift_form.html', event=event, shift=None)


@app.route('/admin/shifts/<int:shift_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if request.method == 'POST':
        shift.name = request.form.get('name', '').strip()
        shift.start_time = request.form.get('start_time', '').strip()
        shift.end_time = request.form.get('end_time', '').strip()
        db.session.commit()
        flash('Dienst bijgewerkt.', 'success')
        return redirect(url_for('admin_event_detail', event_id=shift.event_id))
    return render_template('admin/shift_form.html', event=shift.event, shift=shift)


@app.route('/admin/shifts/<int:shift_id>/delete', methods=['POST'])
@login_required
def admin_delete_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    event_id = shift.event_id
    db.session.delete(shift)
    db.session.commit()
    flash('Dienst verwijderd.', 'info')
    return redirect(url_for('admin_event_detail', event_id=event_id))


# --- Tasks ---

@app.route('/admin/shifts/<int:shift_id>/tasks/new', methods=['GET', 'POST'])
@login_required
def admin_new_task(shift_id):
    shift = Shift.query.get_or_404(shift_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        max_volunteers = request.form.get('max_volunteers', '1').strip()
        if not name:
            flash('Taaknaam is verplicht.', 'danger')
        else:
            task = Task(
                shift_id=shift_id,
                name=name,
                description=description,
                max_volunteers=int(max_volunteers) if max_volunteers.isdigit() else 1,
            )
            db.session.add(task)
            db.session.commit()
            flash('Taak toegevoegd.', 'success')
            return redirect(url_for('admin_event_detail', event_id=shift.event_id))
    return render_template('admin/task_form.html', shift=shift, task=None)


@app.route('/admin/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        task.name = request.form.get('name', '').strip()
        task.description = request.form.get('description', '').strip()
        max_vol = request.form.get('max_volunteers', '1').strip()
        task.max_volunteers = int(max_vol) if max_vol.isdigit() else 1
        db.session.commit()
        flash('Taak bijgewerkt.', 'success')
        return redirect(url_for('admin_event_detail', event_id=task.shift.event_id))
    return render_template('admin/task_form.html', shift=task.shift, task=task)


@app.route('/admin/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def admin_delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    event_id = task.shift.event_id
    db.session.delete(task)
    db.session.commit()
    flash('Taak verwijderd.', 'info')
    return redirect(url_for('admin_event_detail', event_id=event_id))


# --- Registrations ---

@app.route('/admin/events/<int:event_id>/registrations')
@login_required
def admin_registrations(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('admin/registrations.html', event=event)


@app.route('/admin/registrations/<int:registration_id>/delete', methods=['POST'])
@login_required
def admin_delete_registration(registration_id):
    reg = Registration.query.get_or_404(registration_id)
    event_id = reg.task.shift.event_id
    db.session.delete(reg)
    db.session.commit()
    flash('Aanmelding verwijderd.', 'info')
    return redirect(url_for('admin_registrations', event_id=event_id))


@app.route('/admin/events/<int:event_id>/export')
@login_required
def admin_export_csv(event_id):
    event = Event.query.get_or_404(event_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Dienst', 'Begintijd', 'Eindtijd', 'Taak', 'Vrijwilliger', 'E-mail', 'Telefoon', 'Aangemeld op'])
    for shift in event.shifts:
        for task in shift.tasks:
            for reg in task.registrations:
                writer.writerow([
                    shift.name,
                    shift.start_time,
                    shift.end_time,
                    task.name,
                    reg.volunteer_name,
                    reg.volunteer_email,
                    reg.volunteer_phone or '',
                    reg.registered_at.strftime('%Y-%m-%d %H:%M'),
                ])
    output.seek(0)
    filename = f"aanmeldingen_{event.name.replace(' ', '_')}_{event.date}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Bootstrap DB
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)
