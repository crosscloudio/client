
#import <Cocoa/Cocoa.h>

extern CFStringRef kLSSharedFileListFavoriteVolumes;
extern CFStringRef kLSSharedFileListFavoriteItems;
extern CFStringRef kLSSharedFileListRecentApplicationItems;
extern CFStringRef kLSSharedFileListRecentDocumentItems; 
extern CFStringRef kLSSharedFileListRecentServerItems;
extern CFStringRef kLSSharedFileListSessionLoginItems; 
extern CFStringRef kLSSharedFileListGlobalLoginItems; 


@interface LaunchServiceHelper : NSObject

+ (BOOL)addItemWithURLToSidebar: (NSURL *)url;

@end
