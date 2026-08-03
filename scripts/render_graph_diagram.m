#import <AppKit/AppKit.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSString *inputPath = argc > 1
            ? [NSString stringWithUTF8String:argv[1]]
            : @"docs/orbitdesk-agent-graph.svg";
        NSString *outputPath = argc > 2
            ? [NSString stringWithUTF8String:argv[2]]
            : @"docs/orbitdesk-agent-graph.png";

        NSImage *source = [[NSImage alloc]
            initWithContentsOfFile:inputPath];

        if (source == nil) {
            NSLog(@"Could not read %@", inputPath);
            return 1;
        }

        NSInteger width = 1400;
        NSInteger height = 900;
        NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc]
            initWithBitmapDataPlanes:NULL
            pixelsWide:width
            pixelsHigh:height
            bitsPerSample:8
            samplesPerPixel:4
            hasAlpha:YES
            isPlanar:NO
            colorSpaceName:NSCalibratedRGBColorSpace
            bytesPerRow:0
            bitsPerPixel:0];

        NSGraphicsContext *context = [NSGraphicsContext
            graphicsContextWithBitmapImageRep:bitmap];
        [NSGraphicsContext saveGraphicsState];
        [NSGraphicsContext setCurrentContext:context];
        [[NSColor whiteColor] setFill];
        NSRectFill(NSMakeRect(0, 0, width, height));
        [source drawInRect:NSMakeRect(0, 0, width, height)
                  fromRect:NSZeroRect
                 operation:NSCompositingOperationSourceOver
                  fraction:1.0];
        [context flushGraphics];
        [NSGraphicsContext restoreGraphicsState];

        NSData *png = [bitmap
            representationUsingType:NSBitmapImageFileTypePNG
            properties:@{}];

        if (![png writeToFile:outputPath atomically:YES]) {
            NSLog(@"Could not write %@", outputPath);
            return 1;
        }

        NSLog(@"Saved graph diagram to %@", outputPath);
    }

    return 0;
}
