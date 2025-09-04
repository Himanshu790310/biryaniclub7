from setuptools import setup, find_packages

setup(
    name="biryani-club",
    version="1.0.0",
    description="Biryani Club Restaurant Management System",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        '': ['templates/*', 'static/*']
    },
    install_requires=[
        "email-validator>=2.3.0",
        "flask>=3.1.2",
        "flask-sqlalchemy>=3.1.1",
        "gunicorn>=23.0.0",
        "pillow>=11.3.0",
        "psycopg2-binary>=2.9.10",
        "pytz>=2025.2",
        "qrcode>=8.2",
        "sqlalchemy>=2.0.43",
        "werkzeug>=3.1.3",
        "requests>=2.31.0",
    ],
    python_requires=">=3.11",
)
