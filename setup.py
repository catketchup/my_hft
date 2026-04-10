from setuptools import setup, find_packages
from pybind11 import get_include
import os

build_dir = os.path.join(os.path.dirname(__file__), 'build')
so_file = [f for f in os.listdir(build_dir) if f.endswith('.so')][0]

setup(
    name='hft_core',
    version='0.1',
    packages=find_packages(),
    data_files=[('', [os.path.join(build_dir, so_file)])],
    include_package_data=True,
)
