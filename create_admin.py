# Save this file strictly as: create_admin.py

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = "arnav_admin"
email = "bhardwajarnav378@gmail.com"
password = "SecureSuperPassword123"

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser {username}...")
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superuser created successfully!")
else:
    print(f"Superuser {username} already exists.")