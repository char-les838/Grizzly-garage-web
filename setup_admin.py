from getpass import getpass
from werkzeug.security import generate_password_hash
import secrets
username=input('Admin username [admin]: ').strip() or 'admin'
pw=getpass('Create admin password (12+ characters): ')
if len(pw)<12: raise SystemExit('Password must be at least 12 characters.')
confirm=getpass('Confirm password: ')
if pw!=confirm: raise SystemExit('Passwords do not match.')
with open('.env','w',encoding='utf-8') as f:
 f.write(f'ADMIN_USERNAME={username}\nADMIN_PASSWORD_HASH={generate_password_hash(pw)}\nFLASK_SECRET_KEY={secrets.token_hex(32)}\nCOOKIE_SECURE=0\nPORT=5000\n')
print('Created .env. For local testing COOKIE_SECURE=0 is needed. Set COOKIE_SECURE=1 behind HTTPS for production.')
