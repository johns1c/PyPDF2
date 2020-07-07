# vim: sw=4:expandtab:foldmethod=marker
#
# Copyright (c) 2006, Mathieu Fenniak
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


"""
Implementation of generic PDF objects (dictionary, number, string, and so on)


postscript objects are one of the following types

integer          sign, digits (also radix notation )
real             allow exponent and decimal point             , 
boolean          'true' or 'false' 
array, packed array   [ ... ] 
string             (... ) also hex <...> and 
name              a word - perhaps with / 
dictionary        <<  >> 
operator          just another word
mark              stores a position on the operand stack
null              'null' 


"""
__author__ = "Mathieu Fenniak"
__author_email__ = "biziqe@mathieu.fenniak.net"

import re
from .utils import readNonWhitespace, RC4_encrypt, skipOverComment
from .utils import b_, u_, chr_, ord_
from .utils import PdfStreamError
import warnings
from . import filters
from . import utils
import decimal
import codecs
import sys
#import debugging
debug = False

ObjectPrefix = b_('/<[tf(n%')


NumberSigns = b_('+-')
NumberChars = b_('+-.0123456789' )
IndirectPattern = re.compile(b_(r"(\d+)\s+(\d+)\s+R[^a-zA-Z]"))
WHITESPACES =  [b' ', b'\n', b'\r', b'\t', b'\x00', b'']  # or end of string
SEPS = [ b'<' , b'[' ]


def readWord(stream):
    result = b''
    curr_pos = stream.tell()
    tok = stream.read(1)
    while tok not in WHITESPACES and tok not in SEPS :
        result += tok  #appalingly slow
        curr_pos = stream.tell()
        tok = stream.read(1)
    stream.seek(-1,1) 
    return result

def readObject(stream, pdf):
    # do a look ahead - reading 10 bytes and returning from whence we came
    # the individual routines will then interpret the stream from the current position
    here = stream.tell()
    stuff = stream.read(20)
    first_char = stuff[0] 
    stream.seek(here)

    # name like objects true, false, null
    if stuff[:4] == b'true' : 
        return BooleanObject.readFromStream(stream)    
    if stuff[:5] == b'false' :  
        return BooleanObject.readFromStream(stream)    
    if stuff[:4] == b'null' :    
        return NullObject.readFromStream(stream)
    if stuff[:2] == b'<<' :
        return DictionaryObject.readFromStream(stream, pdf)
    if stuff[:2] == b'<~' :
        print( 'pdf stream has ascii85 encoded strings within stream' )
        raise        
    if stuff[:1]  == b'<' :   # old 1 
        try:
            return readHexStringFromStream(stream)
        except :
            print( "########################error reading hex stream following <<" ) 
            stream.seek(spos)
            stuff = stream.read(50) 
            print(stuff)
            raise
    if stuff[:1]  == b'('   : # string  (xxx) old 5
        return readStringFromStream(stream)
    if stuff[:1]  == b'[' :   # array   [...]  old 2
        return ArrayObject.readFromStream(stream, pdf)
        
    if stuff[:1]  == b'%':     # comment old 7 
        # comment
        while tok not in (b_('\r'), b_('\n')):
            tok = stream.read(1)
            # Prevents an infinite loop by raising an error if the stream is at
            # the EOF
            if len(tok) <= 0:
                raise PdfStreamError("File ended unexpectedly.")
        tok = readNonWhitespace(stream)
        stream.seek(-1, 1)
        return readObject(stream, pdf)
        
    if stuff[:1] in NumberChars :
        if IndirectPattern.match(stuff) is not  None:
            return IndirectObject.readFromStream(stream, pdf)
        else :    
            return NumberObject.readFromStream(stream)
        
    if stuff[:1] == b'/'   :
        return NameObject.readFromStream(stream, pdf)
    else :
        
        return readWord(stream) 

class PdfObject(object):
    def getObject(self):
        """Resolves indirect references."""
        return self


class NullObject(PdfObject):
    def writeToStream(self, stream, encryption_key):
        stream.write(b_("null"))

    def readFromStream(stream):
        nulltxt = stream.read(4)
        if nulltxt != b_("null"):
            raise utils.PdfReadError("Could not read Null object")
        return NullObject()
    readFromStream = staticmethod(readFromStream)


class BooleanObject(PdfObject):
    def __init__(self, value):
        self.value = value
        
        
    def __str__( self) :
        return(  "PyPDF2 generic boolean {}".format( self.value ) )

    def __repr__( self) :
        return(  "PyPDF2 generic boolean {}".format( self.value ) )

    def writeToStream(self, stream, encryption_key):
        if self.value:
            stream.write(b_("true"))
        else:
            stream.write(b_("false"))

    def readFromStream(stream):
        word = stream.read(4)
        if word == b_("true"):
            return BooleanObject(True)
        elif word == b_("fals"):
            stream.read(1)
            return BooleanObject(False)
        else:
            raise utils.PdfReadError('Could not read Boolean object')
    readFromStream = staticmethod(readFromStream)


class ArrayObject(list, PdfObject):
    def writeToStream(self, stream, encryption_key):
        stream.write(b_("["))
        for data in self:
            stream.write(b_(" "))
            data.writeToStream(stream, encryption_key)
        stream.write(b_(" ]"))

    def readFromStream(stream, pdf):
        arr = ArrayObject()
        tmp = stream.read(1)
        if tmp != b_("["):
            raise utils.PdfReadError("Could not read array")
        while True:
            # skip leading whitespace
            tok = stream.read(1)
            while tok.isspace():
                tok = stream.read(1)
            #stream.seek(-1, 1)
            # check for array ending
            #tok = stream.read(1)
            if tok == b_("]"):
                break
            stream.seek(-1, 1)  #restored  cj2019 as it stops error
            # read and append obj
            arr.append(readObject(stream, pdf))
        return arr
    readFromStream = staticmethod(readFromStream)


class IndirectObject(PdfObject):
    def __init__(self, idnum, generation, pdf):
        self.idnum = idnum
        self.generation = generation
        self.pdf = pdf

    def getObject(self):
        return self.pdf.getObject(self).getObject()

    def __repr__(self):
        return "IndirectObject(%r, %r)" % (self.idnum, self.generation)

    def __eq__(self, other):
        return (
            other != None and
            isinstance(other, IndirectObject) and
            self.idnum == other.idnum and
            self.generation == other.generation and
            self.pdf is other.pdf
            )

    def __ne__(self, other):
        return not self.__eq__(other)

    def writeToStream(self, stream, encryption_key):
        stream.write(b_("%s %s R" % (self.idnum, self.generation)))

    def readFromStream(stream, pdf):
        idnum = b_("")
        while True:
            tok = stream.read(1)
            if not tok:
                # stream has truncated prematurely
                raise PdfStreamError("Stream has ended unexpectedly")
            if tok.isspace():
                break
            idnum += tok
        generation = b_("")
        while True:
            tok = stream.read(1)
            if not tok:
                # stream has truncated prematurely
                raise PdfStreamError("Stream has ended unexpectedly")
            if tok.isspace():
                if not generation:
                    continue
                break
            generation += tok
        r = readNonWhitespace(stream)
        if r != b_("R"):
            raise utils.PdfReadError("Error reading indirect object reference at byte %s" % utils.hexStr(stream.tell()))
        return IndirectObject(int(idnum), int(generation), pdf)
    readFromStream = staticmethod(readFromStream)


class FloatObject(decimal.Decimal, PdfObject):
    def __new__(cls, value="0", context=None):
        try:
            return decimal.Decimal.__new__(cls, utils.str_(value), context)
        except:
            return decimal.Decimal.__new__(cls, str(value))

    def __repr__(self):
        if self == self.to_integral():
            return str(self.quantize(decimal.Decimal(1)))
        else:
            # Standard formatting adds useless extraneous zeros.
            o = "%.5f" % self
            # Remove the zeros.
            while o and o[-1] == '0':
                o = o[:-1]
            return o

    def as_numeric(self):
        return float(b_(repr(self)))

    def writeToStream(self, stream, encryption_key):
        stream.write(b_(repr(self)))


class NumberObject(int, PdfObject):
    NumberPattern = re.compile(b_('[^+-.0-9]'))
    ByteDot = b_(".")

    def __new__(cls, value):
        val = int(value)
        try:
            return int.__new__(cls, val)
        except OverflowError:
            return int.__new__(cls, 0)

    def as_numeric(self):
        return int(b_(repr(self)))

    def writeToStream(self, stream, encryption_key):
        stream.write(b_(repr(self)))

    def readFromStream(stream):
        num = utils.readUntilRegex(stream, NumberObject.NumberPattern)
        if num.find(NumberObject.ByteDot) != -1:
            return FloatObject(num)
        else:
            return NumberObject(num)
    readFromStream = staticmethod(readFromStream)


##
# Given a string (either a "str" or "unicode"), create a ByteStringObject or a
# TextStringObject to represent the string.
def createStringObject(string):
    # see createStringObjectOrig  - 
    # now everything is a byte stream unless it is specifically indicated as unicode
    #
    # should only get unicode text or bytestreams 
    if isinstance(string, utils.string_type):
        return TextStringObject(string)
    elif string.startswith(codecs.BOM_UTF16_BE):
        retval = TextStringObject(string.decode("utf-16"))
        retval.autodetect_utf16 = True
        return retval
    else:
        return ByteStringObject(string)
def createStringObjectOrig(string):
    if isinstance(string, utils.string_type):
        return TextStringObject(string)
    elif isinstance(string, utils.bytes_type):
        try:
            if string.startswith(codecs.BOM_UTF16_BE):
                retval = TextStringObject(string.decode("utf-16"))
                retval.autodetect_utf16 = True
                return retval
            else:
                # This is probably a big performance hit here, but we need to
                # convert string objects into the text/unicode-aware version if
                # possible... and the only way to check if that's possible is
                # to try.  Some strings are strings, some are just byte arrays.
                retval = TextStringObject(decode_pdfdocencoding(string))
                retval.autodetect_pdfdocencoding = True
                return retval
        except UnicodeDecodeError:
            return ByteStringObject(string)
    else:
        raise TypeError("createStringObject should have str or unicode arg")

def skipWhitespace(stream):
    WHITESPACES =  [b' ', b'\n', b'\r', b'\t', b'\x00', b'%']
    curr_pos = stream.tell()
    tok = WHITESPACES[0]
    while tok in WHITESPACES:
        if tok == b'%':                # comment is whitespace
            tok = readline( stream )
            tok = stream.read(1) 
        else :  
            tok = stream.read(1)
        curr_pos = stream.tell()
    stream.seek(-1,1) 

def readHexStringFromStream(stream):
    stream.read(1)
    txt = ""
    x = b_("")
    while True:
        tok = readNonWhitespace(stream)
        if not tok:
            # stream has truncated prematurely
            raise PdfStreamError("Stream has ended unexpectedly")
        if tok == b_(">"):
            break
        x += tok
        if len(x) == 2:
            txt += chr(int(x, base=16))
            x = b_("")
    if len(x) == 1:
        x += b_("0")
    if len(x) == 2:
        txt += chr(int(x, base=16))
    return( b_(txt))    
    #return createStringObject(b_(txt))


def readStringFromStream(stream):
    tok = stream.read(1)
    parens = 1
    txt = b_("")
    while True:
        tok = stream.read(1)
        if not tok:
            # stream has truncated prematurely
            raise PdfStreamError("Stream has ended unexpectedly")
        if tok == b_("("):
            parens += 1
        elif tok == b_(")"):
            parens -= 1
            if parens == 0:
                break
        elif tok == b_("\\"):
            tok = stream.read(1)
            if tok == b_("n"):
                tok = b_("\n")
            elif tok == b_("r"):
                tok = b_("\r")
            elif tok == b_("t"):
                tok = b_("\t")
            elif tok == b_("b"):
                tok = b_("\b")
            elif tok == b_("f"):
                tok = b_("\f")
            elif tok == b_("c"):
                tok = b_("\c")
            elif tok == b_("("):
                tok = b_("(")
            elif tok == b_(")"):
                tok = b_(")")
            elif tok == b_("/"):
                tok = b_("/")
            elif tok == b_("\\"):
                tok = b_("\\")
            elif tok in (b_(" "), b_("/"), b_("%"), b_("<"), b_(">"), b_("["), 
                    b_("]"), b_("#"),  b_("_"), b_("&"), b_('$')):
                # odd/unnessecary escape sequences we have encountered
                tok = b_(tok)
            elif tok.isdigit():
                # "The number ddd may consist of one, two, or three
                # octal digits; high-order overflow shall be ignored.
                # Three octal digits shall be used, with leading zeros
                # as needed, if the next character of the string is also
                # a digit." (PDF reference 7.3.4.2, p 16)
                for i in range(2):
                    ntok = stream.read(1)
                    if ntok.isdigit():
                        tok += ntok
                    else:
                        break
                tok = b_(chr(int(tok, base=8)))
            elif tok in b_("\n\r"):
                # This case is  hit when a backslash followed by a line
                # break occurs.  If it's a multi-char EOL, consume the
                # second character:
                tok = stream.read(1)
                if not tok in b_("\n\r"):
                    stream.seek(-1, 1)
                # Then don't add anything to the actual string, since this
                # line break was escaped:
                tok = b_('')
            else:
                raise utils.PdfReadError(r"Unexpected escaped string: %s" % tok)
        txt += tok
    return createStringObject(txt)


##
# Represents a string object where the text encoding could not be determined.
# This occurs quite often, as the PDF spec doesn't provide an alternate way to
# represent strings -- for example, the encryption data stored in files (like
# /O) is clearly not text, but is still stored in a "String" object.
class ByteStringObject(utils.bytes_type, PdfObject):

    ##
    # For compatibility with TextStringObject.original_bytes.  This method
    # returns self.
    original_bytes = property(lambda self: self)

    def writeToStream(self, stream, encryption_key):
        bytearr = self
        if encryption_key:
            bytearr = RC4_encrypt(encryption_key, bytearr)
        stream.write(b_("<"))
        stream.write(utils.hexencode(bytearr))
        stream.write(b_(">"))


##
# Represents a string object that has been decoded into a real unicode string.
# If read from a PDF document, this string appeared to match the
# PDFDocEncoding, or contained a UTF-16BE BOM mark to cause UTF-16 decoding to
# occur.
class TextStringObject(utils.string_type, PdfObject):
    autodetect_pdfdocencoding = False
    autodetect_utf16 = False

    ##
    # It is occasionally possible that a text string object gets created where
    # a byte string object was expected due to the autodetection mechanism --
    # if that occurs, this "original_bytes" property can be used to
    # back-calculate what the original encoded bytes were.
    original_bytes = property(lambda self: self.get_original_bytes())

    def get_original_bytes(self):
        # We're a text string object, but the library is trying to get our raw
        # bytes.  This can happen if we auto-detected this string as text, but
        # we were wrong.  It's pretty common.  Return the original bytes that
        # would have been used to create this object, based upon the autodetect
        # method.
        if self.autodetect_utf16:
            return codecs.BOM_UTF16_BE + self.encode("utf-16be")
        elif self.autodetect_pdfdocencoding:
            return encode_pdfdocencoding(self)
        else:
            raise Exception("no information about original bytes")

    def writeToStream(self, stream, encryption_key):
        # Try to write the string out as a PDFDocEncoding encoded string.  It's
        # nicer to look at in the PDF file.  Sadly, we take a performance hit
        # here for trying...
        try:
            bytearr = encode_pdfdocencoding(self)
        except UnicodeEncodeError:
            bytearr = codecs.BOM_UTF16_BE + self.encode("utf-16be")
        if encryption_key:
            bytearr = RC4_encrypt(encryption_key, bytearr)
            obj = ByteStringObject(bytearr)
            obj.writeToStream(stream, None)
        else:
            stream.write(b_("("))
            for c in bytearr:
                if not chr_(c).isalnum() and c != b_(' '):
                    stream.write(b_("\\%03o" % ord_(c)))
                else:
                    stream.write(b_(chr_(c)))
            stream.write(b_(")"))


class NameObject(str, PdfObject):
    delimiterPattern = re.compile(b_(r"\s+|[\(\)<>\[\]{}/%]"))
    surfix = b_("/")

    def writeToStream(self, stream, encryption_key):
        stream.write(b_(self))

    def readFromStream(stream, pdf):
        debug = False
        if debug: print((stream.tell()))
        name = stream.read(1)
        if name != NameObject.surfix:
            raise utils.PdfReadError("name read error")
        name += utils.readUntilRegex(stream, NameObject.delimiterPattern, 
            ignore_eof=True)
        if debug: print(name)
        try:
            return NameObject(name.decode('utf-8'))
        except (UnicodeEncodeError, UnicodeDecodeError) as e:
            # Name objects should represent irregular characters
            # with a '#' followed by the symbol's hex number
            if not pdf.strict:
                warnings.warn("Illegal character in Name Object", utils.PdfReadWarning)
                return NameObject(name)
            else:
                raise utils.PdfReadError("Illegal character in Name Object")

    readFromStream = staticmethod(readFromStream)


class DictionaryObject(dict, PdfObject):
    def raw_get(self, key):
        return dict.__getitem__(self, key)

    def __setitem__(self, key, value):
        if not isinstance(key, PdfObject):
            raise ValueError("key must be PdfObject")
        if not isinstance(value, PdfObject):
            raise ValueError("value must be PdfObject")
        return dict.__setitem__(self, key, value)

    def setdefault(self, key, value=None):
        if not isinstance(key, PdfObject):
            raise ValueError("key must be PdfObject")
        if not isinstance(value, PdfObject):
            raise ValueError("value must be PdfObject")
        return dict.setdefault(self, key, value)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key).getObject()
        except KeyError:
            return None

    ##
    # Retrieves XMP (Extensible Metadata Platform) data relevant to the
    # this object, if available.
    # <p>
    # Stability: Added in v1.12, will exist for all future v1.x releases.
    # @return Returns a {@link #xmp.XmpInformation XmlInformation} instance
    # that can be used to access XMP metadata from the document.  Can also
    # return None if no metadata was found on the document root.
    def getXmpMetadata(self):
        metadata = self.get("/Metadata", None)
        if metadata == None:
            return None
        metadata = metadata.getObject()
        from . import xmp
        if not isinstance(metadata, xmp.XmpInformation):
            metadata = xmp.XmpInformation(metadata)
            self[NameObject("/Metadata")] = metadata
        return metadata

    ##
    # Read-only property that accesses the {@link
    # #DictionaryObject.getXmpData getXmpData} function.
    # <p>
    # Stability: Added in v1.12, will exist for all future v1.x releases.
    xmpMetadata = property(lambda self: self.getXmpMetadata(), None, None)

    def writeToStream(self, stream, encryption_key):
        stream.write(b_("<<\n"))
        for key, value in list(self.items()):
            key.writeToStream(stream, encryption_key)
            stream.write(b_(" "))
            value.writeToStream(stream, encryption_key)
            stream.write(b_("\n"))
        stream.write(b_(">>"))

    def readFromStream(stream, pdf):
        
        db_here = stream.tell()
        db_first = stream.read(250)
        stream.seek( db_here )         
        #debug = True
        # Dictionary starts with line <<
        tmp = stream.read(2)
        if tmp != b_("<<"):
            raise utils.PdfReadError("Dictionary read error at byte %s: stream must begin with '<<'" % utils.hexStr(stream.tell()))
            
        # now bump past any white space or <eol>    
        data = {}
        
        #deal with the dict portion
        while True:      
            tok = readNonWhitespace(stream)
            # cj2019 line below read if not tok
            if tok is None :  
                # stream has truncated prematurely
                raise PdfStreamError("Stream has ended unexpectedly in dict")
            if tok == b_(">"):
                stream.read(1)
                break
            if tok == b_('\x00'):
                continue
            elif tok == b_('%'):
                stream.seek(-1, 1)
                skipOverComment(stream)
                continue
                
            stream.seek(-1, 1)
            key = readObject(stream, pdf)
            tok = readNonWhitespace(stream)
            stream.seek(-1, 1)
            value = readObject(stream, pdf)
            #import pdb
            #pdb.set_trace()
            if not data.get(key):
                data[key] = value
            elif pdf.strict:
                # multiple definitions of key not permitted
                raise utils.PdfReadError("Multiple definitions in dictionary at byte %s for key %s" \
                                           % (utils.hexStr(stream.tell()), key))
            else:
                warnings.warn("Multiple definitions in dictionary at byte %s for key %s" \
                                           % (utils.hexStr(stream.tell()), key), utils.PdfReadWarning)
        
        db_here = stream.tell()

        pos = stream.tell()
        s = readNonWhitespace(stream)
        if s == b_('s') and stream.read(5) == b_('tream'):
            eol = stream.read(1)
            # odd PDF file output has spaces after 'stream' keyword but before EOL.
            # patch provided by Danial Sandler
            while eol == b_(' '):
                eol = stream.read(1)
            assert eol in (b_("\n"), b_("\r"))
            if eol == b_("\r"):
                # read \n after
                if stream.read(1)  != b_('\n'):
                    stream.seek(-1, 1)
            # this is a stream object, not a dictionary
            assert "/Length" in data
            length = data["/Length"]
            if debug: print(data)
            if isinstance(length, IndirectObject):
                t = stream.tell()
                length = pdf.getObject(length)
                stream.seek(t, 0)
            #
            #   
            if True: 
                data_pos = stream.tell()
                term_pos = data_pos + length
                stream.seek(term_pos)
                terminator = stream.readline(200)
                #print( "Data followed by ", terminator )
                #print( "Data length      ", length )
                #print(data)  
                if b'endstream' in terminator:
                    print('OK' )
                else:
                    more_stuff = stream.read(50)
                    #print("More stuff" , more_stuff )
                    stream.seek(term_pos - 30 )
                    less_stuff = stream.read(50) 
                    #print("Less stuff" , less_stuff )
                stream.seek(data_pos)
                
            data["__streamdata__"] = stream.read(length)#cj 17 June
            e = readNonWhitespace(stream)
            ndstream = stream.read(8)
            if (e + ndstream) != b_("endstream"):
                # (sigh) - the odd PDF file has a length that is too long, so
                # we need to read backwards to find the "endstream" ending.
                # ReportLab (unknown version) generates files with this bug,
                # and Python users into PDF files tend to be our audience.
                # we need to do this to correct the streamdata and chop off
                # an extra character.
                print( "Logic error - expecting endstream " , e +ndstream )
                print( pos - 10 )
                pos = stream.tell()
                stream.seek(-10, 1)
                end = stream.read(9)
                if end == b_("endstream"):
                    # we found it by looking back one character further.
                    data["__streamdata__"] = data["__streamdata__"][:-1]
                elif "/Filter" in data :
                    print( "ignoring endstream mismatch " )
                else:
                    if debug: print(("E", e, ndstream, debugging.toHex(end)))
                    stream.seek(pos, 0)
                    raise utils.PdfReadError("Unable to find 'endstream' marker after stream at byte %s." % utils.hexStr(stream.tell()))
        else:
            stream.seek(pos, 0)
        if "__streamdata__" in data:
            return StreamObject.initializeFromDictionary(data)
        else:
            retval = DictionaryObject()
            retval.update(data)
            return retval
    readFromStream = staticmethod(readFromStream)


class TreeObject(DictionaryObject):
    def __init__(self):
        DictionaryObject.__init__(self)

    def hasChildren(self):
        return '/First' in self

    def __iter__(self):
        return self.children()

    def children(self):
        if not self.hasChildren():
            raise StopIteration

        child = self['/First']
        while True:
            yield child
            if child == self['/Last']:
                raise StopIteration
            child = child['/Next']

    def addChild(self, child, pdf):
        childObj = child.getObject()
        child = pdf.getReference(childObj)
        assert isinstance(child, IndirectObject)

        if '/First' not in self:
            self[NameObject('/First')] = child
            self[NameObject('/Count')] = NumberObject(0)
            prev = None
        else:
            prev = self['/Last']

        self[NameObject('/Last')] = child
        self[NameObject('/Count')] = NumberObject(self[NameObject('/Count')] + 1)

        if prev:
            prevRef = pdf.getReference(prev)
            assert isinstance(prevRef, IndirectObject)
            childObj[NameObject('/Prev')] = prevRef
            prev[NameObject('/Next')] = child

        parentRef = pdf.getReference(self)
        assert isinstance(parentRef, IndirectObject)
        childObj[NameObject('/Parent')] = parentRef

    def removeChild(self, child):
        childObj = child.getObject()

        if NameObject('/Parent') not in childObj:
            raise ValueError("Removed child does not appear to be a tree item")
        elif childObj[NameObject('/Parent')] != self:
            raise ValueError("Removed child is not a member of this tree")

        found = False
        prevRef = None
        prev = None
        curRef = self[NameObject('/First')]
        cur = curRef.getObject()
        lastRef = self[NameObject('/Last')]
        last = lastRef.getObject()
        while cur != None:
            if cur == childObj:
                if prev == None:
                    if NameObject('/Next') in cur:
                        # Removing first tree node
                        nextRef = cur[NameObject('/Next')]
                        next = nextRef.getObject()
                        del next[NameObject('/Prev')]
                        self[NameObject('/First')] = nextRef
                        self[NameObject('/Count')] = self[NameObject('/Count')] - 1

                    else:
                        # Removing only tree node
                        assert self[NameObject('/Count')] == 1
                        del self[NameObject('/Count')]
                        del self[NameObject('/First')]
                        if NameObject('/Last') in self:
                            del self[NameObject('/Last')]
                else:
                    if NameObject('/Next') in cur:
                        # Removing middle tree node
                        nextRef = cur[NameObject('/Next')]
                        next = nextRef.getObject()
                        next[NameObject('/Prev')] = prevRef
                        prev[NameObject('/Next')] = nextRef
                        self[NameObject('/Count')] = self[NameObject('/Count')] - 1
                    else:
                        # Removing last tree node
                        assert cur == last
                        del prev[NameObject('/Next')]
                        self[NameObject('/Last')] = prevRef
                        self[NameObject('/Count')] = self[NameObject('/Count')] - 1
                found = True
                break

            prevRef = curRef
            prev = cur
            if NameObject('/Next') in cur:
                curRef = cur[NameObject('/Next')]
                cur = curRef.getObject()
            else:
                curRef = None
                cur = None

        if not found:
            raise ValueError("Removal couldn't find item in tree")

        del childObj[NameObject('/Parent')]
        if NameObject('/Next') in childObj:
            del childObj[NameObject('/Next')]
        if NameObject('/Prev') in childObj:
            del childObj[NameObject('/Prev')]

    def emptyTree(self):
        for child in self:
            childObj = child.getObject()
            del childObj[NameObject('/Parent')]
            if NameObject('/Next') in childObj:
                del childObj[NameObject('/Next')]
            if NameObject('/Prev') in childObj:
                del childObj[NameObject('/Prev')]

        if NameObject('/Count') in self:
            del self[NameObject('/Count')]
        if NameObject('/First') in self:
            del self[NameObject('/First')]
        if NameObject('/Last') in self:
            del self[NameObject('/Last')]


class StreamObject(DictionaryObject):
    def __init__(self):
        self._data = None
        self.decodedSelf = None

    def writeToStream(self, stream, encryption_key):
        self[NameObject("/Length")] = NumberObject(len(self._data))
        DictionaryObject.writeToStream(self, stream, encryption_key)
        del self["/Length"]
        stream.write(b_("\nstream\n"))
        data = self._data
        if encryption_key:
            data = RC4_encrypt(encryption_key, data)
        stream.write(data)
        stream.write(b_("\nendstream"))

    def initializeFromDictionary(data):
        if "/Filter" in data:
            retval = EncodedStreamObject()
        else:
            retval = DecodedStreamObject()
        retval._data = data["__streamdata__"]
        del data["__streamdata__"]
        del data["/Length"]
        retval.update(data)
        return retval
    initializeFromDictionary = staticmethod(initializeFromDictionary)

    def flateEncode(self):
        if "/Filter" in self:
            f = self["/Filter"]
            if isinstance(f, ArrayObject):
                f.insert(0, NameObject("/FlateDecode"))
            else:
                newf = ArrayObject()
                newf.append(NameObject("/FlateDecode"))
                newf.append(f)
                f = newf
        else:
            f = NameObject("/FlateDecode")
        retval = EncodedStreamObject()
        retval[NameObject("/Filter")] = f
        retval._data = filters.FlateDecode.encode(self._data)
        return retval


class DecodedStreamObject(StreamObject):
    def getData(self):
        return self._data

    def setData(self, data):
        self._data = data


class EncodedStreamObject(StreamObject):
    def __init__(self):
        self.decodedSelf = None

    def getData(self):
        if self.decodedSelf:
            # cached version of decoded object
            return self.decodedSelf.getData()
        else:
            # create decoded object
            decoded = DecodedStreamObject()

            decoded._data = filters.decodeStreamData(self)
            for key, value in list(self.items()):
                if not key in ("/Length", "/Filter", "/DecodeParms"):
                    decoded[key] = value
            self.decodedSelf = decoded
            return decoded._data

    def setData(self, data):
        raise utils.PdfReadError("Creating EncodedStreamObject is not currently supported")


class RectangleObject(ArrayObject):
    """
    This class is used to represent *page boxes* in PyPDF2. These boxes include:

        * :attr:`artBox <PyPDF2.pdf.PageObject.artBox>`
        * :attr:`bleedBox <PyPDF2.pdf.PageObject.bleedBox>`
        * :attr:`cropBox <PyPDF2.pdf.PageObject.cropBox>`
        * :attr:`mediaBox <PyPDF2.pdf.PageObject.mediaBox>`
        * :attr:`trimBox <PyPDF2.pdf.PageObject.trimBox>`
    """
    def __init__(self, arr):
        # must have four points
        assert len(arr) == 4
        # automatically convert arr[x] into NumberObject(arr[x]) if necessary
        ArrayObject.__init__(self, [self.ensureIsNumber(x) for x in arr])

    def ensureIsNumber(self, value):
        if not isinstance(value, (NumberObject, FloatObject)):
            value = FloatObject(value)
        return value

    def __repr__(self):
        return "RectangleObject(%s)" % repr(list(self))

    def getLowerLeft_x(self):
        return self[0]

    def getLowerLeft_y(self):
        return self[1]

    def getUpperRight_x(self):
        return self[2]

    def getUpperRight_y(self):
        return self[3]

    def getUpperLeft_x(self):
        return self.getLowerLeft_x()

    def getUpperLeft_y(self):
        return self.getUpperRight_y()

    def getLowerRight_x(self):
        return self.getUpperRight_x()

    def getLowerRight_y(self):
        return self.getLowerLeft_y()

    def getLowerLeft(self):
        return self.getLowerLeft_x(), self.getLowerLeft_y()

    def getLowerRight(self):
        return self.getLowerRight_x(), self.getLowerRight_y()

    def getUpperLeft(self):
        return self.getUpperLeft_x(), self.getUpperLeft_y()

    def getUpperRight(self):
        return self.getUpperRight_x(), self.getUpperRight_y()

    def setLowerLeft(self, value):
        self[0], self[1] = [self.ensureIsNumber(x) for x in value]

    def setLowerRight(self, value):
        self[2], self[1] = [self.ensureIsNumber(x) for x in value]

    def setUpperLeft(self, value):
        self[0], self[3] = [self.ensureIsNumber(x) for x in value]

    def setUpperRight(self, value):
        self[2], self[3] = [self.ensureIsNumber(x) for x in value]

    def getWidth(self):
        return self.getUpperRight_x() - self.getLowerLeft_x()

    def getHeight(self):
        return self.getUpperRight_y() - self.getLowerLeft_y()

    lowerLeft = property(getLowerLeft, setLowerLeft, None, None)
    """
    Property to read and modify the lower left coordinate of this box
    in (x,y) form.
    """
    lowerRight = property(getLowerRight, setLowerRight, None, None)
    """
    Property to read and modify the lower right coordinate of this box
    in (x,y) form.
    """
    upperLeft = property(getUpperLeft, setUpperLeft, None, None)
    """
    Property to read and modify the upper left coordinate of this box
    in (x,y) form.
    """
    upperRight = property(getUpperRight, setUpperRight, None, None)
    """
    Property to read and modify the upper right coordinate of this box
    in (x,y) form.
    """


class Field(TreeObject):
    """
    A class representing a field dictionary. This class is accessed through
    :meth:`getFields()<PyPDF2.PdfFileReader.getFields>`
    """
    def __init__(self, data):
        DictionaryObject.__init__(self)
        attributes = ("/FT", "/Parent", "/Kids", "/T", "/TU", "/TM", "/Ff",
                      "/V", "/DV", "/AA")
        for attr in attributes:
            try:
                self[NameObject(attr)] = data[attr]
            except KeyError:
                pass

    fieldType = property(lambda self: self.get("/FT"))
    """
    Read-only property accessing the type of this field.
    """

    parent = property(lambda self: self.get("/Parent"))
    """
    Read-only property accessing the parent of this field.
    """

    kids = property(lambda self: self.get("/Kids"))
    """
    Read-only property accessing the kids of this field.
    """

    name = property(lambda self: self.get("/T"))
    """
    Read-only property accessing the name of this field.
    """

    altName = property(lambda self: self.get("/TU"))
    """
    Read-only property accessing the alternate name of this field.
    """

    mappingName = property(lambda self: self.get("/TM"))
    """
    Read-only property accessing the mapping name of this field. This
    name is used by PyPDF2 as a key in the dictionary returned by
    :meth:`getFields()<PyPDF2.PdfFileReader.getFields>`
    """

    flags = property(lambda self: self.get("/Ff"))
    """
    Read-only property accessing the field flags, specifying various
    characteristics of the field (see Table 8.70 of the PDF 1.7 reference).
    """

    value = property(lambda self: self.get("/V"))
    """
    Read-only property accessing the value of this field. Format
    varies based on field type.
    """

    defaultValue = property(lambda self: self.get("/DV"))
    """
    Read-only property accessing the default value of this field.
    """

    additionalActions = property(lambda self: self.get("/AA"))
    """
    Read-only property accessing the additional actions dictionary.
    This dictionary defines the field's behavior in response to trigger events.
    See Section 8.5.2 of the PDF 1.7 reference.
    """


class Destination(TreeObject):
    """
    A class representing a destination within a PDF file.
    See section 8.2.1 of the PDF 1.6 reference.

    :param str title: Title of this destination.
    :param int page: Page number of this destination.
    :param str typ: How the destination is displayed.
    :param args: Additional arguments may be necessary depending on the type.
    :raises PdfReadError: If destination type is invalid.

    Valid ``typ`` arguments (see PDF spec for details):
             /Fit       No additional arguments
             /XYZ       [left] [top] [zoomFactor]
             /FitH      [top]
             /FitV      [left]
             /FitR      [left] [bottom] [right] [top]
             /FitB      No additional arguments
             /FitBH     [top]
             /FitBV     [left]
    """
    def __init__(self, title, page, typ, *args):
        DictionaryObject.__init__(self)
        self[NameObject("/Title")] = title
        self[NameObject("/Page")] = page
        self[NameObject("/Type")] = typ

        # from table 8.2 of the PDF 1.7 reference.
        if typ == "/XYZ":
            (self[NameObject("/Left")], self[NameObject("/Top")],
                self[NameObject("/Zoom")]) = args
        elif typ == "/FitR":
            (self[NameObject("/Left")], self[NameObject("/Bottom")],
                self[NameObject("/Right")], self[NameObject("/Top")]) = args
        elif typ in ["/FitH", "/FitBH"]:
            self[NameObject("/Top")], = args
        elif typ in ["/FitV", "/FitBV"]:
            self[NameObject("/Left")], = args
        elif typ in ["/Fit", "/FitB"]:
            pass
        else:
            raise utils.PdfReadError("Unknown Destination Type: %r" % typ)

    def getDestArray(self):
        return ArrayObject([self.raw_get('/Page'), self['/Type']] + [self[x] for x in ['/Left', '/Bottom', '/Right', '/Top', '/Zoom'] if x in self])

    def writeToStream(self, stream, encryption_key):
        stream.write(b_("<<\n"))
        key = NameObject('/D')
        key.writeToStream(stream, encryption_key)
        stream.write(b_(" "))
        value = self.getDestArray()
        value.writeToStream(stream, encryption_key)

        key = NameObject("/S")
        key.writeToStream(stream, encryption_key)
        stream.write(b_(" "))
        value = NameObject("/GoTo")
        value.writeToStream(stream, encryption_key)

        stream.write(b_("\n"))
        stream.write(b_(">>"))

    title = property(lambda self: self.get("/Title"))
    """
    Read-only property accessing the destination title.

    :rtype: str
    """

    page = property(lambda self: self.get("/Page"))
    """
    Read-only property accessing the destination page number.

    :rtype: int
    """

    typ = property(lambda self: self.get("/Type"))
    """
    Read-only property accessing the destination type.

    :rtype: str
    """

    zoom = property(lambda self: self.get("/Zoom", None))
    """
    Read-only property accessing the zoom factor.

    :rtype: int, or ``None`` if not available.
    """

    left = property(lambda self: self.get("/Left", None))
    """
    Read-only property accessing the left horizontal coordinate.

    :rtype: int, or ``None`` if not available.
    """

    right = property(lambda self: self.get("/Right", None))
    """
    Read-only property accessing the right horizontal coordinate.

    :rtype: int, or ``None`` if not available.
    """

    top = property(lambda self: self.get("/Top", None))
    """
    Read-only property accessing the top vertical coordinate.

    :rtype: int, or ``None`` if not available.
    """

    bottom = property(lambda self: self.get("/Bottom", None))
    """
    Read-only property accessing the bottom vertical coordinate.

    :rtype: int, or ``None`` if not available.
    """


class Bookmark(Destination):
    def writeToStream(self, stream, encryption_key):
        stream.write(b_("<<\n"))
        for key in [NameObject(x) for x in ['/Title', '/Parent', '/First', '/Last', '/Next', '/Prev'] if x in self]:
            key.writeToStream(stream, encryption_key)
            stream.write(b_(" "))
            value = self.raw_get(key)
            value.writeToStream(stream, encryption_key)
            stream.write(b_("\n"))
        key = NameObject('/Dest')
        key.writeToStream(stream, encryption_key)
        stream.write(b_(" "))
        value = self.getDestArray()
        value.writeToStream(stream, encryption_key)
        stream.write(b_("\n"))
        stream.write(b_(">>"))

def decode_pdfdocencoding( byte_array ) :
    return decode_builtin( byte_array ,  '/PDFDocEncoding' ) 
    
def encode_pdfdocencoding(unicode_string):
    retval = b_('')
    for c in unicode_string:
        try:
            retval += b_(chr(_pdfDocEncoding_rev[c]))
        except KeyError:
            raise UnicodeEncodeError("pdfdocencoding", c, -1, -1,
                    "does not exist in translation table")
    return retval
 
def decode_builtin( byte_array ,  encoding ): 
 
    if 'PDFDoc' in encoding :
        decode_table = _pdfDocEncoding
    elif 'Standard' in encoding :
        decode_table  =  _standard_encoding
    elif 'WinAnsi' in encoding :
       return byte_array.decide('cp1252')
    elif 'MacRoman' in encoding :
        decode_table  =  _roman_encoding 
    elif 'Symbol' in encoding :
        decode_table  =  _symbol_encoding
    elif 'dingbat' in encoding :
        decode_table  =  _dingbat_encoding
    else :
        return byte_array.decide( encoding)

    
    retval = u_('')
    for b in byte_array:
        c = decode_table[ord_(b)]
        if c == u_('\u0000'):
            raise UnicodeDecodeError("pdfdocencoding", utils.barray(b), -1, -1,
                    "does not exist in translation table")
        retval += c
    return retval

_standard_encoding =[
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u00A0','\u0021','\u0022','\u0023','\u0024','\u0025','\u0026','\u2019',
'\u0028','\u0029','\u002A','\u002B','\u002C','\u00AD','\u002E','\u002F',
'\u0030','\u0031','\u0032','\u0033','\u0034','\u0035','\u0036','\u0037',
'\u0038','\u0039','\u003A','\u003B','\u003C','\u003D','\u003E','\u003F',
'\u0040','\u0041','\u0042','\u0043','\u0044','\u0045','\u0046','\u0047',
'\u0048','\u0049','\u004A','\u004B','\u004C','\u004D','\u004E','\u004F',
'\u0050','\u0051','\u0052','\u0053','\u0054','\u0055','\u0056','\u0057',
'\u0058','\u0059','\u005A','\u005B','\u005C','\u005D','\u005E','\u005F',
'\u2018','\u0061','\u0062','\u0063','\u0064','\u0065','\u0066','\u0067',
'\u0068','\u0069','\u006A','\u006B','\u006C','\u006D','\u006E','\u006F',
'\u0070','\u0071','\u0072','\u0073','\u0074','\u0075','\u0076','\u0077',
'\u0078','\u0079','\u007A','\u007B','\u007C','\u007D','\u007E','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u00A1','\u00A2','\u00A3','\u2215','\u00A5','\u0192','\u00A7',
'\u00A4','\u0027','\u201C','\u00AB','\u2039','\u203A','\uFB01','\uFB02',
'\u0000','\u2013','\u2020','\u2021','\u2219','\u0000','\u00B6','\u2022',
'\u201A','\u201E','\u201D','\u00BB','\u2026','\u2030','\u0000','\u00BF',
'\u0000','\u0060','\u00B4','\u02C6','\u02DC','\u02C9','\u02D8','\u02D9',
'\u00A8','\u0000','\u02DA','\u00B8','\u0000','\u02DD','\u02DB','\u02C7',
'\u2014','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u00C6','\u0000','\u00AA','\u0000','\u0000','\u0000','\u0000',
'\u0141','\u00D8','\u0152','\u00BA','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u00E6','\u0000','\u0000','\u0000','\u0131','\u0000','\u0000',
'\u0142','\u00F8','\u0153','\u00DF','\u0000','\u0000','\u0000','\u0000']
_symbol_encoding =[
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u00A0','\u0021','\u2200','\u0023','\u2203','\u0025','\u0026','\u220B',
'\u0028','\u0029','\u2217','\u002B','\u002C','\u2212','\u002E','\u002F',
'\u0030','\u0031','\u0032','\u0033','\u0034','\u0035','\u0036','\u0037',
'\u0038','\u0039','\u003A','\u003B','\u003C','\u003D','\u003E','\u003F',
'\u2245','\u0391','\u0392','\u03A7','\u2206','\u0395','\u03A6','\u0393',
'\u0397','\u0399','\u03D1','\u039A','\u039B','\u039C','\u039D','\u039F',
'\u03A0','\u0398','\u03A1','\u03A3','\u03A4','\u03A5','\u03C2','\u2126',
'\u039E','\u03A8','\u0396','\u005B','\u2234','\u005D','\u22A5','\u005F',
'\uF8E5','\u03B1','\u03B2','\u03C7','\u03B4','\u03B5','\u03C6','\u03B3',
'\u03B7','\u03B9','\u03D5','\u03BA','\u03BB','\u03BC','\u03BD','\u03BF',
'\u03C0','\u03B8','\u03C1','\u03C3','\u03C4','\u03C5','\u03D6','\u03C9',
'\u03BE','\u03C8','\u03B6','\u007B','\u007C','\u007D','\u223C','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u20AC','\u03D2','\u2032','\u2264','\u2215','\u221E','\u0192','\u2663',
'\u2666','\u2665','\u2660','\u2194','\u2190','\u2191','\u2192','\u2193',
'\u00B0','\u00B1','\u2033','\u2265','\u00D7','\u221D','\u2202','\u2022',
'\u00F7','\u2260','\u2261','\u2248','\u2026','\uF8E6','\uF8E7','\u21B5',
'\u2135','\u2111','\u211C','\u2118','\u2297','\u2295','\u2205','\u2229',
'\u222A','\u2283','\u2287','\u2284','\u2282','\u2286','\u2208','\u2209',
'\u2220','\u2207','\uF6DA','\uF6D9','\uF6DB','\u220F','\u221A','\u22C5',
'\u00AC','\u2227','\u2228','\u21D4','\u21D0','\u21D1','\u21D2','\u21D3',
'\u25CA','\u2329','\uF8E8','\uF8E9','\uF8EA','\u2211','\uF8EB','\uF8EC',
'\uF8ED','\uF8EE','\uF8EF','\uF8F0','\uF8F1','\uF8F2','\uF8F3','\uF8F4',
'\u0000','\u232A','\u222B','\u2320','\uF8F5','\u2321','\uF8F6','\uF8F7',
'\uF8F8','\uF8F9','\uF8FA','\uF8FB','\uF8FC','\uF8FD','\uF8FE','\u0000']
_dingbat_encoding =[
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u00A0','\u2701','\u2702','\u2703','\u2704','\u260E','\u2706','\u2707',
'\u2708','\u2709','\u261B','\u261E','\u270C','\u270D','\u270E','\u270F',
'\u2710','\u2711','\u2712','\u2713','\u2714','\u2715','\u2716','\u2717',
'\u2718','\u2719','\u271A','\u271B','\u271C','\u271D','\u271E','\u271F',
'\u2720','\u2721','\u2722','\u2723','\u2724','\u2725','\u2726','\u2727',
'\u2605','\u2729','\u272A','\u272B','\u272C','\u272D','\u272E','\u272F',
'\u2730','\u2731','\u2732','\u2733','\u2734','\u2735','\u2736','\u2737',
'\u2738','\u2739','\u273A','\u273B','\u273C','\u273D','\u273E','\u273F',
'\u2740','\u2741','\u2742','\u2743','\u2744','\u2745','\u2746','\u2747',
'\u2748','\u2749','\u274A','\u274B','\u25CF','\u274D','\u25A0','\u274F',
'\u2750','\u2751','\u2752','\u25B2','\u25BC','\u25C6','\u2756','\u25D7',
'\u2758','\u2759','\u275A','\u275B','\u275C','\u275D','\u275E','\u0000',
'\uF8D7','\uF8D8','\uF8D9','\uF8DA','\uF8DB','\uF8DC','\uF8DD','\uF8DE',
'\uF8DF','\uF8E0','\uF8E1','\uF8E2','\uF8E3','\uF8E4','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u2761','\u2762','\u2763','\u2764','\u2765','\u2766','\u2767',
'\u2663','\u2666','\u2665','\u2660','\u2460','\u2461','\u2462','\u2463',
'\u2464','\u2465','\u2466','\u2467','\u2468','\u2469','\u2776','\u2777',
'\u2778','\u2779','\u277A','\u277B','\u277C','\u277D','\u277E','\u277F',
'\u2780','\u2781','\u2782','\u2783','\u2784','\u2785','\u2786','\u2787',
'\u2788','\u2789','\u278A','\u278B','\u278C','\u278D','\u278E','\u278F',
'\u2790','\u2791','\u2792','\u2793','\u2794','\u2192','\u2194','\u2195',
'\u2798','\u2799','\u279A','\u279B','\u279C','\u279D','\u279E','\u279F',
'\u27A0','\u27A1','\u27A2','\u27A3','\u27A4','\u27A5','\u27A6','\u27A7',
'\u27A8','\u27A9','\u27AA','\u27AB','\u27AC','\u27AD','\u27AE','\u27AF',
'\u0000','\u27B1','\u27B2','\u27B3','\u27B4','\u27B5','\u27B6','\u27B7',
'\u27B8','\u27B9','\u27BA','\u27BB','\u27BC','\u27BD','\u27BE','\u0000']
_roman_encoding =[
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000','\u0000',
'\u0020','\u0021','\u0022','\u0023','\u0024','\u0025','\u0026','\u0027',
'\u0028','\u0029','\u002A','\u002B','\u002C','\u002D','\u002E','\u002F',
'\u0030','\u0031','\u0032','\u0033','\u0034','\u0035','\u0036','\u0037',
'\u0038','\u0039','\u003A','\u003B','\u003C','\u003D','\u003E','\u003F',
'\u0040','\u0041','\u0042','\u0043','\u0044','\u0045','\u0046','\u0047',
'\u0048','\u0049','\u004A','\u004B','\u004C','\u004D','\u004E','\u004F',
'\u0050','\u0051','\u0052','\u0053','\u0054','\u0055','\u0056','\u0057',
'\u0058','\u0059','\u005A','\u005B','\u005C','\u005D','\u005E','\u005F',
'\u0060','\u0061','\u0062','\u0063','\u0064','\u0065','\u0066','\u0067',
'\u0068','\u0069','\u006A','\u006B','\u006C','\u006D','\u006E','\u006F',
'\u0070','\u0071','\u0072','\u0073','\u0074','\u0075','\u0076','\u0077',
'\u0078','\u0079','\u007A','\u007B','\u007C','\u007D','\u007E','\u0000',
'\u00C4','\u00C5','\u00C7','\u00C9','\u00D1','\u00D6','\u00DC','\u00E1',
'\u00E0','\u00E2','\u00E4','\u00E3','\u00E5','\u00E7','\u00E9','\u00E8',
'\u00EA','\u00EB','\u00ED','\u00EC','\u00EE','\u00EF','\u00F1','\u00F3',
'\u00F2','\u00F4','\u00F6','\u00F5','\u00FA','\u00F9','\u00FB','\u00FC',
'\u2020','\u00B0','\u00A2','\u00A3','\u00A7','\u2022','\u00B6','\u00DF',
'\u00AE','\u00A9','\u2122','\u00B4','\u00A8','\u2260','\u00C6','\u00D8',
'\u221E','\u00B1','\u2264','\u2265','\u00A5','\u00B5','\u2202','\u2211',
'\u220F','\u03C0','\u222B','\u00AA','\u00BA','\u03A9','\u00E6','\u00F8',
'\u00BF','\u00A1','\u00AC','\u221A','\u0192','\u2248','\u2206','\u00AB',
'\u00BB','\u2026','\u00A0','\u00C0','\u00C3','\u00D5','\u0152','\u0153',
'\u2013','\u2014','\u201C','\u201D','\u2018','\u2019','\u00F7','\u25CA',
'\u00FF','\u0178','\u2044','\u20AC','\u2039','\u203A','\uFB01','\uFB02',
'\u2021','\u00B7','\u201A','\u201E','\u2030','\u00C2','\u00CA','\u00C1',
'\u00CB','\u00C8','\u00CD','\u00CE','\u00CF','\u00CC','\u00D3','\u00D4',
'\uF8FF','\u00D2','\u00DA','\u00DB','\u00D9','\u0131','\u02C6','\u02DC',
'\u00AF','\u02D8','\u02D9','\u02DA','\u00B8','\u02DD','\u02DB','\u02C7']
    
_pdfDocEncoding = (
  u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'),
  u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'),
  u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'), u_('\u0000'),
  u_('\u02d8'), u_('\u02c7'), u_('\u02c6'), u_('\u02d9'), u_('\u02dd'), u_('\u02db'), u_('\u02da'), u_('\u02dc'),
  u_('\u0020'), u_('\u0021'), u_('\u0022'), u_('\u0023'), u_('\u0024'), u_('\u0025'), u_('\u0026'), u_('\u0027'),
  u_('\u0028'), u_('\u0029'), u_('\u002a'), u_('\u002b'), u_('\u002c'), u_('\u002d'), u_('\u002e'), u_('\u002f'),
  u_('\u0030'), u_('\u0031'), u_('\u0032'), u_('\u0033'), u_('\u0034'), u_('\u0035'), u_('\u0036'), u_('\u0037'),
  u_('\u0038'), u_('\u0039'), u_('\u003a'), u_('\u003b'), u_('\u003c'), u_('\u003d'), u_('\u003e'), u_('\u003f'),
  u_('\u0040'), u_('\u0041'), u_('\u0042'), u_('\u0043'), u_('\u0044'), u_('\u0045'), u_('\u0046'), u_('\u0047'),
  u_('\u0048'), u_('\u0049'), u_('\u004a'), u_('\u004b'), u_('\u004c'), u_('\u004d'), u_('\u004e'), u_('\u004f'),
  u_('\u0050'), u_('\u0051'), u_('\u0052'), u_('\u0053'), u_('\u0054'), u_('\u0055'), u_('\u0056'), u_('\u0057'),
  u_('\u0058'), u_('\u0059'), u_('\u005a'), u_('\u005b'), u_('\u005c'), u_('\u005d'), u_('\u005e'), u_('\u005f'),
  u_('\u0060'), u_('\u0061'), u_('\u0062'), u_('\u0063'), u_('\u0064'), u_('\u0065'), u_('\u0066'), u_('\u0067'),
  u_('\u0068'), u_('\u0069'), u_('\u006a'), u_('\u006b'), u_('\u006c'), u_('\u006d'), u_('\u006e'), u_('\u006f'),
  u_('\u0070'), u_('\u0071'), u_('\u0072'), u_('\u0073'), u_('\u0074'), u_('\u0075'), u_('\u0076'), u_('\u0077'),
  u_('\u0078'), u_('\u0079'), u_('\u007a'), u_('\u007b'), u_('\u007c'), u_('\u007d'), u_('\u007e'), u_('\u0000'),
  u_('\u2022'), u_('\u2020'), u_('\u2021'), u_('\u2026'), u_('\u2014'), u_('\u2013'), u_('\u0192'), u_('\u2044'),
  u_('\u2039'), u_('\u203a'), u_('\u2212'), u_('\u2030'), u_('\u201e'), u_('\u201c'), u_('\u201d'), u_('\u2018'),
  u_('\u2019'), u_('\u201a'), u_('\u2122'), u_('\ufb01'), u_('\ufb02'), u_('\u0141'), u_('\u0152'), u_('\u0160'),
  u_('\u0178'), u_('\u017d'), u_('\u0131'), u_('\u0142'), u_('\u0153'), u_('\u0161'), u_('\u017e'), u_('\u0000'),
  u_('\u20ac'), u_('\u00a1'), u_('\u00a2'), u_('\u00a3'), u_('\u00a4'), u_('\u00a5'), u_('\u00a6'), u_('\u00a7'),
  u_('\u00a8'), u_('\u00a9'), u_('\u00aa'), u_('\u00ab'), u_('\u00ac'), u_('\u0000'), u_('\u00ae'), u_('\u00af'),
  u_('\u00b0'), u_('\u00b1'), u_('\u00b2'), u_('\u00b3'), u_('\u00b4'), u_('\u00b5'), u_('\u00b6'), u_('\u00b7'),
  u_('\u00b8'), u_('\u00b9'), u_('\u00ba'), u_('\u00bb'), u_('\u00bc'), u_('\u00bd'), u_('\u00be'), u_('\u00bf'),
  u_('\u00c0'), u_('\u00c1'), u_('\u00c2'), u_('\u00c3'), u_('\u00c4'), u_('\u00c5'), u_('\u00c6'), u_('\u00c7'),
  u_('\u00c8'), u_('\u00c9'), u_('\u00ca'), u_('\u00cb'), u_('\u00cc'), u_('\u00cd'), u_('\u00ce'), u_('\u00cf'),
  u_('\u00d0'), u_('\u00d1'), u_('\u00d2'), u_('\u00d3'), u_('\u00d4'), u_('\u00d5'), u_('\u00d6'), u_('\u00d7'),
  u_('\u00d8'), u_('\u00d9'), u_('\u00da'), u_('\u00db'), u_('\u00dc'), u_('\u00dd'), u_('\u00de'), u_('\u00df'),
  u_('\u00e0'), u_('\u00e1'), u_('\u00e2'), u_('\u00e3'), u_('\u00e4'), u_('\u00e5'), u_('\u00e6'), u_('\u00e7'),
  u_('\u00e8'), u_('\u00e9'), u_('\u00ea'), u_('\u00eb'), u_('\u00ec'), u_('\u00ed'), u_('\u00ee'), u_('\u00ef'),
  u_('\u00f0'), u_('\u00f1'), u_('\u00f2'), u_('\u00f3'), u_('\u00f4'), u_('\u00f5'), u_('\u00f6'), u_('\u00f7'),
  u_('\u00f8'), u_('\u00f9'), u_('\u00fa'), u_('\u00fb'), u_('\u00fc'), u_('\u00fd'), u_('\u00fe'), u_('\u00ff')
)


_pdfDocEncoding_rev = {}
for i in range(256):
    char = _pdfDocEncoding[i]
    if char == u_("\u0000"):
        continue
    assert char not in _pdfDocEncoding_rev
    _pdfDocEncoding_rev[char] = i
