#from PyPDF2 import pdf
import PyPDF2,_utils as utils
from PyPDF2._reader import DocumentInformation, PdfFileReader
from PyPDF2._version import __version__
from PyPDF2._writer import PdfFileWriter
from PyPDF2._merger import PdfFileMerger
from PyPDF2.pagerange import PageRange, parse_filename_page_ranges
from PyPDF2.papersizes import PaperSize
from PyPDF2.toUnicode import toUnicode
from PyPDF2._page import Transformation

__all__ = [
    "__version__",
    "PageRange",
    "PaperSize",
    "DocumentInformation",
    "parse_filename_page_ranges",
    "pdf",
    "PdfFileMerger",
    "PdfFileReader",
    "PdfFileWriter",
    "toUnicode",
    "Transformation",
    "utils", 
]
