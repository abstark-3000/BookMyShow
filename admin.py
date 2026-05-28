import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Production credentials configuration
username = "arnav_admin"
email = "bhardwajarnav378@gmail.com"
password = "SecureSuperPassword123"  # Feel free to change this password

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser {username}...")
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superuser created successfully!")
else:
    print(f"Superuser {username} already exists.")