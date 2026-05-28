import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get('ADMIN_USERNAME', 'arnav_admin')
email = os.environ.get('ADMIN_EMAIL', 'bhardwajarnav378@gmail.com')
password = os.environ.get('ADMIN_PASSWORD', 'SecureSuperPassword123')

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser {username}...")
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superuser created successfully!")
else:
    print(f"Superuser {username} already exists.")