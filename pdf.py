# -*- coding: utf-8 -*-
#
# todo
#
#  allow indirect objects to replace integer and other values
#  using code similar to that for rotation
#  translate all the standard encodings properly
#
#
# Original Copyright 2006, Mathieu Fenniak
# Copyright (c) 2007, Ashish Kulkarni <kulkarni.ashish@gmail.com>
# Changes Martin Thoma and others March 2022 onwards
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# * The name of the author may not be used to endorse or promote products
# derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""This module is deprecated. Import from PyPDF2 or PyPDF2.errors directly."""

__author__ = "Mathieu Fenniak"
__author_email__ = "biziqe@mathieu.fenniak.net"


from PyPDF2._page import *  # noqa: F401
from PyPDF2._reader import *  # noqa: F401
from PyPDF2._writer import *  # noqa: F401


from PyPDF2.constants import CatalogAttributes as CA  # noqa: F401
from PyPDF2.constants import Core as CO  # noqa: F401
from PyPDF2.constants import PageAttributes as PG  # noqa: F401
from PyPDF2.constants import PagesAttributes as PA  # noqa: F401
from PyPDF2.constants import Ressources as RES  # noqa: F401
from PyPDF2.constants import StreamAttributes as SA  # noqa: F401
from PyPDF2.constants import TrailerKeys as TK  # noqa: F401
from PyPDF2.errors import (  # noqa: F401
    PageSizeNotDefinedError,
    PdfReadError,
    PdfReadWarning,
)

from . import _utils  # noqa: F401
from .generic import *  # noqa: F401
from .toUnicode import *  # noqa: F401
from ._utils import (  # noqa: F401
    ConvertFunctionsToVirtualList,
    b_,
    formatWarning,
    isString,
    ord_,
    readNonWhitespace,
    readUntilWhitespace,
    str_,
    u_,
)
