//
//  FinderSync.swift
//  CrossCloud Extension
//
//  Created by Christoph Hechenblaikner
//  Copyright (c) 2016 CrossCloud GmbH. All rights reserved.
//

import Cocoa
import FinderSync
import CoreFoundation


class FinderSync: FIFinderSync
{
    //labels for badeges of items
    let SYNCING_LABEL: String = "Syncing"
    let SYNCED_LABEL: String = "Synced"
    let ERROR_LABEL: String = "Error"
    
    // the communication interface to the sync core
    var syncCore: IPCSyncCore
    
    //flag indicating if updating shall be stopped
    var isUpdateSyncStateActive : Bool = false;
    static let SYNC_STATUS_UPDATE_PERIOD_SECONDS: UInt32 = 1
    
    // syncing directory (default: ~/CrossCloud)
    var isUpdateSyncDirActive : Bool = false;
    static let SYNC_DIR_UPDATE_PERIOD_SECONDS: UInt32 = 15
    
    // the url of the received sync dir
    var syncDir : URL?
    
    // mapping of action id tags to actio ids -> this is needed as a bug(?) does
    //not preserve the representedObject value of NSMenuItem when being returned as sender in the corresponding action
    var actionTagIdMapping : [Int: String] = [Int: String]()
    
    override init()
    {
        print("FinderSync() launched from \(Bundle.main.bundlePath)")
        
        // ignoring SIGPIPE signals from outside. If the core connection server stops - we are trying to write to a fd that is close, which
        // which is why we get this signal -> but we don't care and reconnect later
        signal(SIGPIPE, SIG_IGN)
        
        // initializing sync core interface
        // getting app container location (only this one is accessible through the sandbox)
        var appContainerUrl = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: IPCSyncCore.APPLICATION_GROUP_ID);
        appContainerUrl?.appendPathComponent(IPCSyncCore.UNIX_DOMAIN_SOCKET_NAME)
        
        // creating and connecting unix socket
        self.syncCore = IPCSyncCore(unixSocketPath: (appContainerUrl?.path)!)
        _ = self.syncCore.connect()
        
        
        // super class initializer after all subclass fields have been initialized
        super.init()
        
        //start polling and updating sync dir from core
        self.startUpdatingSyncDir()
        
        //set up labels to display
        FIFinderSyncController.default().setBadgeImage(NSImage(named: "syncing.png")!, label: SYNCING_LABEL , forBadgeIdentifier: SYNCING_LABEL)
        FIFinderSyncController.default().setBadgeImage(NSImage(named: "synced.png")!, label: SYNCED_LABEL, forBadgeIdentifier: SYNCED_LABEL)
        
        // start updating sync status
        self.startUpdatingSyncStatus()
    }
    
    // MARK: - Sync state update functions
    
    /**
     starts updating the sync status from the core
     **/
    fileprivate func startUpdatingSyncStatus()
    {
        print("starting updating sync status")
        if(self.isUpdateSyncStateActive == false)
        {
            //creating and starting background update thread
            self.isUpdateSyncStateActive = true;
            
            DispatchQueue.global(qos: .background).async
                {
                    while(self.isUpdateSyncStateActive == true)
                    {
                        if let statusUpdate = self.syncCore.getPathStatusUpdates()
                        {
                            // updating sync status
                            self.processSyncStatusUpdate(statusUpdate: statusUpdate)
                        }
                        
                        // wait for next poll
                        sleep(FinderSync.SYNC_STATUS_UPDATE_PERIOD_SECONDS)
                    }
            }
        }
    }
    
    /**
     starts updating sync dir
     **/
    fileprivate func startUpdatingSyncDir()
    {
        if(self.isUpdateSyncDirActive == false)
        {
            //creating and starting background update thread
            self.isUpdateSyncDirActive = true;
            DispatchQueue.global(qos: .background).async
                {
                    while(self.isUpdateSyncDirActive == true)
                    {
                        // updating sync status
                        self.updateSyncDir()
                        
                        // wait for next poll
                        sleep(FinderSync.SYNC_DIR_UPDATE_PERIOD_SECONDS)
                    }
            }
        }
    }
    
    fileprivate func stopUpdatingSyncStatus()
    {
        print("stopping updating sync status from core")
        self.isUpdateSyncStateActive = false
    }
    
    fileprivate func stopUpdatingSyncDir()
    {
        print("stopping updating sync dir from core")
        self.isUpdateSyncDirActive = false
    }
    
    /**
     processes an update of paths that was received
     **/
    func processSyncStatusUpdate(statusUpdate: [PathUpdate])
    {
        //setting new status for items
        for update in statusUpdate
        {
            // updating item iself
            let pathUrl = URL(fileURLWithPath: update.path)
            FIFinderSyncController.default().setBadgeIdentifier(update.status, for: URL(fileURLWithPath: update.path))
            
            // updating parent items
            self.checkDirStatusUp(startPath: pathUrl)
            
        }
    }
    
    
    /**
     triggers a check for all directories upwards from startPath -> triggers get status calls
     **/
    func checkDirStatusUp(startPath: URL)
    {
        // just to make sure we have a sync dir at this point (timing -> update before sync dir)
        if self.syncDir == nil
        {
            return
        }
        
        let syncDirParent: URL = self.syncDir!.deletingLastPathComponent()
        var currentPath: URL = startPath
        
        var safeguard = 1000;
        
        //iterating over path until CC dir is reached
        //conditions: 1) not sync dir parent already 2) not empty path 3) safeguard not fired
        while(currentPath != syncDirParent && currentPath.pathComponents.count > 0 && safeguard > 0)
        {
            // getting new status for directory
            if let dirStatus = self.syncCore.getPathStatus(path: currentPath.path)
            {
                // setting dir status
                FIFinderSyncController.default().setBadgeIdentifier(dirStatus, for: currentPath)
            }
            else
            {
                break
            }
            
            //removing last path component = one level up
            currentPath = currentPath.deletingLastPathComponent()
            safeguard -= 1;
        }
    }
    
    /**
     fetches sync dir path from server and sets FinderSync to that path.
     **/
    fileprivate func updateSyncDir()
    {
        // Set up the directories we are syncing.
        if let syncdir = self.syncCore.getSyncDirectory()
        {
            let fetchedSyncDir : URL = URL(fileURLWithPath:syncdir);
            if (fetchedSyncDir.path.isEmpty == false && ((self.syncDir == nil) || ((self.syncDir! != fetchedSyncDir))))
            {
                print("Got new syncdir \(fetchedSyncDir.description)")
                //setting new sync dir
                self.syncDir = fetchedSyncDir;
                
                //adding syncdir to watched dirs of finder
                FIFinderSyncController.default().directoryURLs.insert(self.syncDir!);
                self.beginObservingDirectory(at: self.syncDir!);
                
                //adding new sync dir to finder sidebar
                // this has been disabled since buggy and creates invalid entries in sidebar -> also deprecated in 10.11
                // http://stackoverflow.com/questions/3517874/programmatically-add-a-folder-to-places-in-finder
                //LaunchServiceHelper.addItemWithURL(toSidebar: fetchedSyncDir)
            }
        }
        else
        {
            print("Got no sync dir");
            if(self.syncDir != nil)
            {
                //removing old syncdir from watched directories
                FIFinderSyncController.default().directoryURLs.remove(self.syncDir!)
            }
            
            // resetting reference
            self.syncDir = nil;
        }
    }
    
    // MARK: - Primary Finder Sync protocol methods
    override func beginObservingDirectory(at url: URL)
    {
        print("beginObservingDirectory \(url.description)")
    }
    
    override func endObservingDirectory(at url: URL)
    {
        print("endObservingDirectory \(url.description)")
    }
    
    override func requestBadgeIdentifier(for url: URL)
    {
        // getting string representation for sync status of item over ipc and setting it for item
        if self.syncCore.coreAvailable == true, let syncStatus = self.syncCore.getPathStatus(path: url.path)
        {
            FIFinderSyncController.default().setBadgeIdentifier(syncStatus, for: url)
        }
        else
        {
            // default case syncing -> don't panic user as stuff is unexpectedly syncing
            FIFinderSyncController.default().setBadgeIdentifier(SYNCED_LABEL, for: url)
        }
    }
    
    // MARK: - Menu and toolbar item support
    override var toolbarItemName: String
    {
        return "";
    }
    
    override var toolbarItemToolTip: String
    {
        return "";
    }
    
    override var toolbarItemImage: NSImage
    {
        return NSImage(named: NSImageNameCaution)!
    }
    
    
    // MARK: - Context Menu methods
    // builds and returns an appropriate menu for the kind requested
    override func menu(for menuKind: FIMenuKind) -> NSMenu
    {
        //get selected items
        if let itemUrls = FIFinderSyncController.default().selectedItemURLs()
        {
            //converting urls to string
            let itemStrings = itemUrls.map({( urlItem) ->
                String in
                return urlItem.path})
            
            //get menu for selected element from core
            if let menuItems = self.syncCore.getContextMenu(selectedPaths: itemStrings)
            {
                // create menu and path mapping
                return self.buildMenu(menuItems: menuItems);
            }
            else
            {
                // returning dummy menu item displaying message
                let menu = NSMenu(title: "")
                menu.addItem(withTitle: "Cannot connect. . .", action: nil, keyEquivalent: "")
                return menu
            }
        }
        else
        {
            // empty menu
            return NSMenu(title: "")
        }
    }
    
    
    /**
     builds a menu according to the provided parameters
     clean tells the function if the action mapping shall be cleaned before execution
     **/
    func buildMenu(menuItems: [MenuItem], clean: Bool = true) -> NSMenu
    {
        return autoreleasepool {() -> NSMenu in
            
            // clearing mappign of action ids
            if(clean == true)
            {
                self.actionTagIdMapping.removeAll()
            }
            
            // creating root menu
            let rootMenu = NSMenu(title: "")
            
            // itarating over menu item
            for menuItem in menuItems
            {
                // setting tag on new item and adding mapping to later identify actionid
                let tagValue = menuItem.actionId.hashValue

                // injecting new menu item into root and setting properties
                let newItem = rootMenu.addItem(withTitle: menuItem.name, action: #selector(executeContextMenuAction), keyEquivalent: "")
                
                // setting enabled and image proerty according to menu item received
                newItem.isEnabled = menuItem.enabled
                
                // setting image based on checked status icon
                if let checked = menuItem.checked
                {
                    if(checked == true)
                    {
                        newItem.image = NSImage(named: "checked.png")!
                    }
                    else
                    {
                        newItem.image = NSImage(named: "unchecked.png")
                    }
                }
                else
                {
                    //setting image only on parent components
                    newItem.image = NSImage(named: "logo.png")
                }
                
                // if no children -> simple menu item with logo and action
                if menuItem.children.isEmpty
                {
                    // this item is an action -> setting action mapping
                    self.actionTagIdMapping[tagValue] = String(menuItem.actionId)
                    
                    // setting action tag item
                    newItem.tag = tagValue
                }
                else
                {
                    // building menu for subitems
                    let submenu = buildMenu(menuItems: menuItem.children, clean: false)
                    
                    // setting submenu to menuitem
                    newItem.submenu = submenu
                }
            }
            
            
            return rootMenu
        }
    }
    
    
    /**
     executes the action as identified by the id
     **/
    func executeContextMenuAction(sender: NSMenuItem)
    {
        autoreleasepool {
            // getting action id string from mapping of tag values (hash values) of the menu object to the actual string
            if let actionIdString = self.actionTagIdMapping[sender.tag]
            {
                
                //getting selected paths
                let selectedItems : [URL] = FIFinderSyncController.default().selectedItemURLs()! as [URL];
                
                //converting urls to string
                let itemStrings = selectedItems.map({(urlItem) -> String in urlItem.path})
                
                //executing command
                self.syncCore.performAction(actionId: actionIdString, selectedPaths: itemStrings)
            }
            
            self.actionTagIdMapping.removeAll()
        }
    }
}

