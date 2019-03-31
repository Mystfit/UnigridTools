import os, shutil

def cleanup_folder(path):
    for f in os.listdir(path):
        f_path = os.path.join(path, f)
        try:
            if os.path.isfile(f_path):
                os.unlink(f_path)
            elif os.path.isdir(f_path): 
                shutil.rmtree(f_path)
        except Exception as e:
            print(e)
