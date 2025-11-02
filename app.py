from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.orm import relationship  # 添加这行
from flask import flash
import os
from werkzeug.utils import secure_filename
from docx import Document

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///homework.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 文件上传配置
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 最大文件大小
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}

# 确保上传目录存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

db = SQLAlchemy(app)


# 使用简化的模型定义
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)

    teacher = db.relationship('User', backref=db.backref('assignments', lazy=True))


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    grade = db.Column(db.String(10), nullable=True)

    assignment = db.relationship('Assignment', backref=db.backref('submissions', lazy=True))
    student = db.relationship('User', backref=db.backref('submissions', lazy=True))

# 创建数据库表
with app.app_context():
    # 仅测试用
    db.drop_all()

    db.create_all()

    # 添加初始测试用户（在实际使用中应该删除这部分）
    if not User.query.filter_by(username='t1').first():
        teacher = User(username='t1', password='123', role='teacher', name='张老师')
        db.session.add(teacher)

    if not User.query.filter_by(username='s1').first():
        student = User(username='s1', password='123', role='student', name='李同学')
        db.session.add(student)

    if not User.query.filter_by(username='s2').first():
        student2 = User(username='s2', password='123', role='student', name='王同学')
        db.session.add(student2)

    db.session.commit()


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    # 如果已登录，直接重定向到对应面板
    if 'user_id' in session and session['role'] == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    elif 'user_id' in session and session['role'] == 'student':
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['name'] = user.name

            if user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            return render_template('login.html', error='用户名或密码错误')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    assignments = Assignment.query.filter_by(teacher_id=session['user_id']).all()
    return render_template('teacher_dashboard.html', assignments=assignments)


@app.route('/teacher/create_assignment', methods=['GET', 'POST'])
def create_assignment():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        due_date_str = request.form['due_date']

        # 转换日期字符串为日期对象
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None

        new_assignment = Assignment(
            title=title,
            content=content,
            teacher_id=session['user_id'],
            due_date=due_date
        )

        db.session.add(new_assignment)
        db.session.commit()

        return redirect(url_for('teacher_dashboard'))

    return render_template('create_assignment.html')


@app.route('/teacher/view_submissions/<int:assignment_id>')
def view_submissions(assignment_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    assignment = Assignment.query.get_or_404(assignment_id)

    # 确保老师只能查看自己发布的作业
    if assignment.teacher_id != session['user_id']:
        return redirect(url_for('teacher_dashboard'))

    # 使用正确的关系访问
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()

    return render_template('view_submissions.html', assignment=assignment, submissions=submissions)


@app.route('/student/dashboard')
def student_dashboard():
    # 检查会话
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('login'))

    if session.get('role') != 'student':
        flash('无权限访问学生面板', 'error')
        return redirect(url_for('login'))

    # 获取所有作业
    assignments = Assignment.query.all()
    assignments_with_status = []

    for assignment in assignments:
        # 检查学生是否已提交该作业
        submission = Submission.query.filter_by(
            assignment_id=assignment.id,
            student_id=session['user_id']
        ).first()

        assignments_with_status.append({
            'assignment': assignment,
            'submitted': submission is not None,
            'submission': submission
        })

    # 添加调试信息
    print(f"找到 {len(assignments)} 个作业")
    print(
        f"学生 {session['user_id']} 的作业状态: {[(item['assignment'].title, item['submitted']) for item in assignments_with_status]}")

    return render_template('student_dashboard.html', assignments=assignments_with_status)


@app.route('/student/submit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
def submit_assignment(assignment_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    assignment = Assignment.query.get_or_404(assignment_id)

    # 检查是否已提交
    existing_submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        student_id=session['user_id']
    ).first()

    if request.method == 'POST':
        content = request.form.get('content', '')
        file = request.files.get('file')

        # 处理文件上传
        file_path = None
        file_name = None

        if file and file.filename:
            if allowed_file(file.filename):
                # 生成安全的文件名
                filename = secure_filename(file.filename)
                # 添加时间戳避免重名
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_')
                unique_filename = f"{timestamp}{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                file_name = filename
                flash('文件上传成功!', 'success')
            else:
                flash('不支持的文件类型。请上传 txt, pdf, doc 或 docx 文件。', 'error')
                return render_template('submit_assignment.html',
                                       assignment=assignment,
                                       submission=existing_submission)

        try:
            if existing_submission:
                # 更新现有提交
                existing_submission.content = content
                if file_path:
                    # 如果之前有文件，删除旧文件
                    if existing_submission.file_path and os.path.exists(existing_submission.file_path):
                        os.remove(existing_submission.file_path)
                    existing_submission.file_path = file_path
                    existing_submission.file_name = file_name
                existing_submission.submitted_at = datetime.utcnow()
                message = '作业提交已更新!'
            else:
                # 创建新提交
                new_submission = Submission(
                    assignment_id=assignment_id,
                    student_id=session['user_id'],
                    content=content,
                    file_path=file_path,
                    file_name=file_name
                )
                db.session.add(new_submission)
                message = '作业提交成功!'

            db.session.commit()
            flash(message, 'success')
            return redirect(url_for('student_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'提交错误: {str(e)}', 'error')

    return render_template('submit_assignment.html',
                           assignment=assignment,
                           submission=existing_submission)


# 注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    # 如果是老师登录，重定向到教师面板
    if 'user_id' in session and session['role'] == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    # 如果是学生登录，重定向到学生面板
    elif 'user_id' in session and session['role'] == 'student':
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        name = request.form['name']

        # 验证输入
        if not username or not password or not confirm_password or not name:
            flash('请填写所有必填字段', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('密码确认不匹配', 'error')
            return render_template('register.html')

        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('用户名已存在，请选择其他用户名', 'error')
            return render_template('register.html')

        # 创建新学生用户
        new_student = User(
            username=username,
            password=password,
            role='student',
            name=name,
        )

        try:
            db.session.add(new_student)
            db.session.commit()
            flash('注册成功！请登录', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('注册失败，请稍后重试', 'error')
            return render_template('register.html')

    return render_template('register.html')


@app.route('/teacher/student_management')
def student_management():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    # 获取所有学生，包括他们的提交信息
    students = User.query.filter_by(role='student').all()
    return render_template('student_management.html', students=students)



@app.route('/download/<int:submission_id>')
def download_file(submission_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    submission = Submission.query.get_or_404(submission_id)

    # 权限检查：老师可以下载任何提交，学生只能下载自己的提交
    if session['role'] == 'student' and submission.student_id != session['user_id']:
        flash('没有权限访问此文件', 'error')
        return redirect(url_for('student_dashboard'))

    if not submission.file_path or not os.path.exists(submission.file_path):
        flash('文件不存在', 'error')
        return redirect(request.referrer or url_for('student_dashboard'))

    # 发送文件
    return send_file(
        submission.file_path,
        as_attachment=True,
        download_name=submission.file_name or f"submission_{submission_id}.docx"
    )


# 添加预览Word文档内容的功能
@app.route('/preview/<int:submission_id>')
def preview_file(submission_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    submission = Submission.query.get_or_404(submission_id)

    # 权限检查
    if session['role'] == 'student' and submission.student_id != session['user_id']:
        flash('没有权限访问此文件', 'error')
        return redirect(url_for('student_dashboard'))

    if not submission.file_path or not os.path.exists(submission.file_path):
        flash('文件不存在', 'error')
        return redirect(request.referrer or url_for('student_dashboard'))

    # 尝试读取Word文档内容
    try:
        if submission.file_path.endswith('.docx'):
            doc = Document(submission.file_path)
            content = ""
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"

            return render_template('file_preview.html',
                                   submission=submission,
                                   content=content,
                                   file_type='Word文档')
        else:
            # 对于其他文件类型，显示基本信息
            return render_template('file_preview.html',
                                   submission=submission,
                                   content="此文件类型不支持在线预览，请下载查看。",
                                   file_type=submission.file_name.split('.')[
                                       -1].upper() if submission.file_name else '未知')

    except Exception as e:
        return render_template('file_preview.html',
                               submission=submission,
                               content=f"文件读取错误: {str(e)}",
                               file_type='错误')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

