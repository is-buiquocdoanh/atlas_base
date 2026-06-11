from setuptools import find_packages, setup
from glob import glob

package_name = 'atlas_app'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Robotics VN',
    maintainer_email='roboticsvn.ai@gmail.com',
    description='Atlas A2 native PyQt5 desktop control app',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'atlas_app = atlas_app.main:main',
        ],
    },
)
