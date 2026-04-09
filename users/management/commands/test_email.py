"""Django management command to test email configuration"""
from django.core.management.base import BaseCommand
from django.conf import settings
from users.email_service import diagnose_email_config, EmailService
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Test email configuration and send a test email'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Email address to send test verification email to'
        )
    
    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("📧 EMAIL CONFIGURATION & TEST TOOL"))
        self.stdout.write("="*70 + "\n")
        
        # Run diagnostic
        diagnose_email_config()
        
        # Test with real email if provided
        email_address = options.get('email')
        if email_address:
            self.stdout.write(f"\n📬 Attempting to send test email to: {email_address}")
            
            # Try to get or create a test user
            try:
                user, created = User.objects.get_or_create(
                    email=email_address,
                    defaults={
                        'name': 'Test User',
                        'role': 'INFLUENCER',
                    }
                )
                
                if created:
                    self.stdout.write(f"✓ Created test user: {user.email}")
                else:
                    self.stdout.write(f"✓ Using existing user: {user.email}")
                
                # Send test email
                success, message = EmailService.send_verification_email(
                    user,
                    token="test-token-123456",
                    code="123456"
                )
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f"\n✅ {message}")
                    )
                    self.stdout.write("   Check your inbox for the verification email!")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"\n❌ {message}")
                    )
                    self.stdout.write("\n" + "="*70)
                    self.stdout.write("SOLUTIONS:")
                    self.stdout.write("="*70)
                    self.print_solutions()
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"\n❌ Error: {str(e)}")
                )
                self.print_solutions()
        else:
            self.stdout.write("\n💡 To test actual email sending, run:")
            self.stdout.write("   python manage.py test_email --email your-email@example.com\n")
    
    def print_solutions(self):
        """Print common solutions"""
        self.stdout.write("""
1. CHECK GMAIL APP PASSWORD:
   - Go to: https://myaccount.google.com/apppasswords
   - Create an "App password" for Django Mail
   - Copy the 16-character password

2. UPDATE YOUR .env FILE:
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-16-char-password  (NOT your regular password!)
   DEBUG_EMAIL=True  (for development)

3. FOR OFFICE 365 / OUTLOOK:
   EMAIL_HOST=smtp.office365.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your-email@company.com
   EMAIL_HOST_PASSWORD=your-password

4. FOR SENDGRID (RECOMMENDED FOR PRODUCTION):
   EMAIL_BACKEND=sendgrid_backend.SendgridBackend
   SENDGRID_API_KEY=your-sendgrid-key
   
   Install: pip install sendgrid-django

5. DEBUG MODE (DEVELOPMENT ONLY):
   - Set DEBUG_EMAIL=True to log emails to console
   - Check Django logs for email content

6. RESTART DJANGO SERVER after changing .env:
   python manage.py runserver
        """)
