import setuptools

def _install_requires(filename):
    return open(filename).read().splitlines()

setuptools.setup(
    name="pysemisecs",
    version="0.5.0",
    license="Apache-2.0",
    author="kenta-shimizu",
    description="This package is SEMI-SECS-communicate implementation on Python3.",
    url="https://github.com/kenta-shimizu/pysemisecs",
    packages=setuptools.find_packages(),
    zip_safe=False,
    install_requires=_install_requires('./requirements.txt')
)
