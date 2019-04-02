import setuptools

setuptools.setup(name='Stitch',
    version='0.1',
    description='UniGrid http stitcher',
    author='Byron Mallett',
    author_email='byron.mallett@vuw.ac.nz',
    packages=setuptools.find_packages(),
    entry_points={'console_scripts': ['StitchServer = Stitch.Server:start_server']},
)
