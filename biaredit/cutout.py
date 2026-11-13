"""Person instance masks for one image -> PNG per instance (full resolution).
Usage: cutout.py image.jpg outdir"""
import sys, os, Quartz, Vision, Foundation
from Quartz import CIImage, CIContext, kCIFormatL8
from Foundation import NSURL
src, out = sys.argv[1], sys.argv[2]
img = Quartz.CGImageSourceCreateImageAtIndex(Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(src), None), 0, None)
h = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
req = Vision.VNGeneratePersonInstanceMaskRequest.alloc().initWithCompletionHandler_(None)
ok, err = h.performRequests_error_([req], None)
obs = req.results()[0]
ctx = CIContext.contextWithOptions_(None)
cs = Quartz.CGColorSpaceCreateDeviceGray()
for idx in obs.allInstances():
    buf, err = obs.generateScaledMaskForImageForInstances_fromRequestHandler_error_(Foundation.NSIndexSet.indexSetWithIndex_(idx), h, None)
    ci = CIImage.imageWithCVPixelBuffer_(buf)
    p = os.path.join(out, f"mask_{idx}.png")
    ctx.writePNGRepresentationOfImage_toURL_format_colorSpace_options_error_(ci, NSURL.fileURLWithPath_(p), kCIFormatL8, cs, None, None)
    print("instance", idx, p)
