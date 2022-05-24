# PyPDF2
PyPDF2 for Python 3 

This is a revised version of PyPDF2 with a number of fixes and extensions 
1)  Python 3  only though may work with 2.7 it has not been tested 
2)  extended character set handling (extract to text works in many cases it did not before) 
3)  bug fixes 
 
The code now includes many of the changes made in 2022 by Martin Thoma and others to the production
PyPDF2.  The code has also been reformatted via Black.  

 But 
*) My code is not the best - symbol naming conventions are mixed
*) Most literals have just been changed to binary strings rather than a more systematic approach
*) testing is not systematic - although I have run a large number of test PDFs through the viewer built on this code
*) No systematic approach to handing Postscript
*) Still not got the codecs exactly matching the spec 

Chris

p.s. Notes byte strings vs unicode  stringson Python 2.7 compatibiliuty

PDF consists of byte-streams.

special characters that indicate, for example the start and end of objects 
are bytestrings.  The b_ function was used to ensure the creation of these
strings in a way that works in both Python 2 and Python  3. 

My understanding is that the  b_ function is no longer needed as the
b string prefix works in both  Python 2.7 and Python 3.  Replacing the
b_ function will get rid on many cases where we are needlessly converting
constant and trivial values between unicode and bytestreams and also get
rid of some cases where we are round-tripping.

One difference between Python 3 bytestrings and  Python 2 strings is that
subscripting in Py3 will give an integer.  Slices are required instead.

PDF Strings are byte-streams

from what I can tell **all** PDF strings are bytestring objects unless they 
start with the specified BOM.  This will apply however the string is 
coded so a string defined in hex should be treated as any other string.

Interpretation of these is dependent on context.

if they represent printable characters they are character ids interpreted according to the
current font (or fonts if using a composite font).  Sometimes the font will expect multibyte
characters and sometimes this will be a according to utf16.

some existing code attempts to recover the original byte string from the decoded text.  This
round tripping does not work in all cases.



