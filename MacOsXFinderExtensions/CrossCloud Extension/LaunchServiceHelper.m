
#import "LaunchServiceHelper.h"
#import <CoreServices/CoreServices.h>

@implementation LaunchServiceHelper

#pragma mark Shared Lists

+ (BOOL) addItemWithURLToSidebar:(NSURL *)url
{
    LSSharedFileListRef list = LSSharedFileListCreate(NULL, kLSSharedFileListFavoriteItems, NULL);
    if (!list) return NO;
    LSSharedFileListItemRef item = LSSharedFileListInsertItemURL(list, 
                                                                 kLSSharedFileListItemBeforeFirst,
                                                                 NULL, NULL, 
                                                                 (__bridge CFURLRef)url,
                                                                 NULL, NULL);
    CFRelease(list);
    CFRelease(item);
    return item ? YES : NO;
}

@end
