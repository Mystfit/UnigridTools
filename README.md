# Uni-grid Tools
## Maya plug-in installation
#### Windows
  - Copy the folder `maya\plug-ins` to `Documents\maya\[YEAR]`
#### OSX
  - Copy the contents of the folder `maya/plug-ins` to `/Users/Shared/Autodesk/maya/[YEAR]/plug-ins`

## Running the plug-in
  - Launch Maya and go to Windows->Settings/Preferences->Plug-in Manager.
  - Next to the plug-in `unigrid.py`, select the `Loaded` checkbox.
  - Make sure you have set your project and loaded your scene.
  - From the top Maya menubar, click `Uni-grid->Show Uni-grid tools`.

## FAQ
### Where are my rendered images?
Click the `Open images folder` button next to your job in the Scene jobs section. Windows users will either be asked for the password for user that ran the job or will use whatever was last entered in the Username and Password fields in the Login section. OSX users will receive a login prompt if they have not already connected to the Uni-grid server in Finder.

### Why do some of my stitched renders have corrupted tiles?
This is a bug. From the Uni-grid tools window menu, click `View->Toggle debug items`, enter your render job ID into the Job ID field and click the `Stitch tiles` button. Wait a minute or two then check your renders again.

### Why did the server reject my job with the error *Frame limit is under 1000 frames*? 
Currently the maximum number of tasks you can submit to Uni-grid is 1000. The total number of tasks in a job can be calculated using the forumla `Tile columns * Tile rows * (End frame - Start frame)`