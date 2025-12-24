from flask import Blueprint, redirect, url_for, request, render_template_string
from flask_login import current_user
from functools import wraps
from . import roles

approval_bp = Blueprint('approval', __name__)

def pending_user_check(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return f(*args, **kwargs)
            
        if roles.is_pending(current_user.role):
            # Allow access to the waiting list page itself and logout and static
            if request.endpoint in ['approval.waiting_list', 'web.logout', 'static']:
                return f(*args, **kwargs)
            return redirect(url_for('approval.waiting_list'))
            
        return f(*args, **kwargs)
    return decorated_function

@approval_bp.route("/waiting-list")
def waiting_list():
    html = """
    <html>
        <head>
            <title>Čekací listina - Calibre-Web</title>
            <style>
                body { background: #0F0F0F; color: #CCCCCC; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding-top: 100px; }
                .card { background: #181818; border: 1px solid #9e2222; padding: 40px; display: inline-block; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); max-width: 500px; }
                h1 { color: #9e2222; margin-bottom: 20px; font-weight: 300; }
                p { line-height: 1.6; color: #BBB; }
                .accent { color: #9e2222; font-weight: bold; }
                hr { border: 0; border-top: 1px solid #333; margin: 20px 0; }
                .btn { display: inline-block; padding: 10px 20px; color: #888; text-decoration: none; border: 1px solid #333; border-radius: 4px; transition: all 0.3s; }
                .btn:hover { border-color: #9e2222; color: #EEE; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Vítejte v Knihovně!</h1>
                <p>Váš účet z fóra <span class="accent">ebookforum.sk</span> byl úspěšně rozpoznán.</p>
                <p>Nyní se nacházíte na <strong>čekací listině</strong>.</p>
                <hr>
                <p>Váš přístup musí být nejprve ručně schválen administrátorem. Po schválení vám bude přidělena odpovídající role (Čtenář, VIP apod.).</p>
                <p>Děkujeme za trpělivost.</p>
                <br>
                <a href="{{ url_for('web.logout') }}" class="btn">Odhlásit se</a>
            </div>
        </body>
    </html>
    """
    return render_template_string(html)
