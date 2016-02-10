#!/usr/bin/perl

# Save forward g729 rtp payload from wireshark to raw file, then
# run this script.
#
# derived from http://wiki.wireshark.org/HowToDecodeG729


$usage = "Usage: '$0 filename.raw' (output will be filename.au)\n(raw file from wireshark g729 rtp payload)";

$srcFile = shift @ARGV || die $usage;
($srcFile1) = ($srcFile =~ /^(.+)\.raw$/i);
die $usage if (! $srcFile1);

die "$srcFile doesn't exist!" if (! -e $srcFile);

die "$srcFile1.au already exists." if (-e "$srcFile1.au");

##

print "creating tmp pcm file\n";
system("wine /home/ryan/bin/va_g729_decoder.exe $srcFile $srcFile1.$$.pcm");
die "va_g729_decoder failed" if (! -e "$srcFile1.$$.pcm");


print "creating output file $srcFile1.au\n";


open(SRCFILE, "$srcFile1.$$.pcm") || die "Unable to open file: $!\n";
binmode SRCFILE;

open(DSTFILE, "> $srcFile1.au") || die "Unable to open file: $!\n";
binmode DSTFILE;

###################################
# Write the AU header
###################################

print DSTFILE  ".snd";

$foo = pack("CCCC", 0,0,0,24);
print DSTFILE  $foo;

$foo = pack("CCCC", 0xff,0xff,0xff,0xff);
print DSTFILE  $foo;

$foo = pack("CCCC", 0,0,0,3);
print DSTFILE  $foo;

$foo = pack("CCCC", 0,0,0x1f,0x40);
print DSTFILE  $foo;

$foo = pack("CCCC", 0,0,0,1);
print DSTFILE  $foo;

#############################
# swap the PCM samples
#############################

while (read(SRCFILE, $inWord, 2) == 2) {

    @bytes   = unpack('CC', $inWord);
    $outWord = pack('CC', $bytes[1], $bytes[0]);
    print DSTFILE  $outWord;
}

close(DSTFILE);
close(SRCFILE);

unlink "$srcFile1.$$.pcm";
