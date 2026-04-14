import json
import os
from django.core.management.base import BaseCommand
from category.models import Category

class Command(BaseCommand):
    help = 'Met à jour les descriptions des catégories existantes à partir du fichier category_niches.json'

    def handle(self, *args, **options):
        # Chemin du fichier JSON
        json_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'category_niches.json'
        )

        if not os.path.exists(json_file_path):
            self.stdout.write(self.style.ERROR(f'JSON file not found at: {json_file_path}'))
            return

        # Lecture du JSON
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading JSON file: {str(e)}'))
            return

        categories = data.get('categories', [])
        updated = 0
        for cat in categories:
            name = cat.get('name')
            description = cat.get('description', '')
            try:
                obj = Category.objects.get(name=name)
                if obj.description != description:
                    obj.description = description
                    obj.save()
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f'Updated: {name}'))
            except Category.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Not found: {name}'))
        self.stdout.write(self.style.SUCCESS(f'\nDescriptions mises à jour pour {updated} catégories.'))
