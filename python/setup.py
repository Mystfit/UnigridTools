import setuptools

setuptools.setup(name='Unigrid',
    version='0.2',
    description='Unigrid tools',
    author='Byron Mallett',
    author_email='byron.mallett@vuw.ac.nz',
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts':
            ['start_stitch_server = Unigrid.server:start_server',
            'stitch_tiles = Unigrid.stitch:run_stitcher',
            'split_tiles = Unigrid.split:run_splitter'
            ]
        },
)
