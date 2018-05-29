# General
This app mainly contains a FinderSyncExtension for CrossCloud.
This extension integrates into the macOS finder and displays batches as well as context values. To do this, this extension communicates with the CrossCloud SyncCore (main component) over a unix-socket using JSON-RPC. The project is based on Swift 3.0 and the FinderSync App Extension interface (https://developer.apple.com/library/content/documentation/General/Conceptual/ExtensibilityPG/).

# Overview
The App is only needed to host the extension, so all interesting is going on in the `CrossCloud Extension` target. The class `FinderSync` implements the `FIFindersyncController` protocol. It configures itself as app extension and implements the required methods to receive information from the Finder. The `FinderSync` class uses the `IPCSyncCore` class to communicate with the sync core and get information to display its information. The extension has two main functions:
a) Display sync badges for files and folders: Upon rendering of each item in an observed folder (configured by `FinderSync`), a delegate method is called in `FinderSync` to get a badge item. `FinderSync` calls an IPC method (`getItemStatus`) to get the status of the item and display it's correct badge. This only happens when the item is rendered. As statuses of items can change, the extension periodically polls for update events from the core. Such updates feature an item (path) and a new status. The extension parses these updates and sets the badges of the items accordingly
b) Context menu: When clicking right, the extension displays a dynamic context menu based on the status of the file and the CrossCloud configuration. Therefore, the app extension gets this dynamic menu from the sync core, displays it and triggers actions back into the sync core.

The communication of the extension and the sync core only happens triggered by the extension at this point. This is why, it is required to poll for changes at this point. The JSON-RPC protocol is used for communication between the extension and the core. The core opens a server over a unix domain socket transport layer, while the socket connects to it.

The app extension is sandboxed which only allows access to certain folders in the file system.

# Memory and performance considerations
As the application performs the same operation (check for updates of files, etc.) periodically, it is essential that operations performed in this periodic loop don't leak memory.

Further, malloced and freed memory, which is not cleaned by the VM comes into play as it makes the memory consumption of the extension very high.

The project uses atoreleasepools (explicit) to keep the memory footprint low.

# External Libraries
At this point, the application uses no external libraries. When adding such, consider switching the project to the swift package manager or Cocoapods.

# Run
1) Build the appliation in XCode
2) Select the CrossCloud Extension as a target and Run
3) Select Finder as the host application to attach to (as this is a FinderSync Extension)
4) The application waits to attach -> usually a restart of finder is required to get the application started.

ATTENTION: When debugging: make sure that only your current version of the FinderSyncExtension is running. As Finder tends to start all .appex files anywhere in the filesystem, multiple instances (old and new ones) of your extension might be running influencing the behavior of the application. 

# Build
TODO
