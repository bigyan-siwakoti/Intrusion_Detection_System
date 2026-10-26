"""Fill the Contents / List of Figures / List of Tables fields and export a PDF with LibreOffice.

    /usr/bin/python3 docs/update_fields.py docs/Final_Report_Group13.docx
Writes <name>.pdf next to the input. The .docx itself is left as built (Word refreshes fields on open).
"""
import subprocess, sys, time, uno
from pathlib import Path
from com.sun.star.beans import PropertyValue

src = Path(sys.argv[1]).resolve()
proc = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore",
                         "--accept=socket,host=localhost,port=2002;urp;"])
ctx = uno.getComponentContext()
resolver = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
for _ in range(60):
    try:
        rctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(1)
desktop = rctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", rctx)
def pv(n, v):
    p = PropertyValue(); p.Name = n; p.Value = v; return p
doc = desktop.loadComponentFromURL(src.as_uri(), "_blank", 0, (pv("Hidden", True),))
for _ in range(2):  # second pass: page numbers settle after the lists take space
    idx = doc.getDocumentIndexes()
    for i in range(idx.getCount()):
        idx.getByIndex(i).update()
    doc.refresh()
doc.storeToURL(src.with_suffix(".pdf").as_uri(), (pv("FilterName", "writer_pdf_Export"),))
# Also save a copy with the Contents / lists filled in, so Word Online (which cannot refresh these fields) shows them.
filled = src.with_name(src.stem + "_filled.docx")
doc.storeToURL(filled.as_uri(), (pv("FilterName", "MS Word 2007 XML"),))
doc.close(True)
try:
    desktop.terminate()
except Exception:
    pass
proc.wait(timeout=30)
print("pdf:", src.with_suffix(".pdf"))
