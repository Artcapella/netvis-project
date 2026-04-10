# abilene-readme.txt
#
# Project: SndLib
#
# Demand matrices from measurements in the U.S Abilene network

*************
Content:
*************

1. Origin
2. Creation
3. Format
4. Remarks
5. Original Abilene Readme

***********************
1. Origin
***********************

The dynamic demand matrices contained in the archives
  - directed-abilene-zhang-5min-over-6months-ALL.tgz        (xml files)
  - directed-abilene-zhang-5min-over-6months-ALL-native.tgz (native format files)
are calculated from real-life accounting data
Abilene network http://www.cs.utexas.edu/~yzhang/research/AbileneTM/.


Original data taken in 5min steps starting on 01.03.2004 at 00:00 and ending on 10.09.2004 
at 23:55 (with several breaks in between, see below).
Topology (including link capacities, OSPF link weights and geographic locations of routers)
and a routing matrix are available.

**** NOTICE: THERE MIGHT BE BUGS IN THE DATA, see Remarks ****

***********************
2. Creation
***********************

The measurement values are converted into MBit/s demand values.
Since the original units are "(100 bytes / 5 minutes)  // 100 is the pkt sampling rate",
each demand value is scaled by /3*8/1000000 to get MBit/s.

- The node name ATLA-M5 is replaced by ATLAM5.
- The measurement (Byte) values are converted to MBit/s demand values
  and rounded to the 6th decimal place.
- Zero demands are removed, that is, traffic
  with value smaller than 0.0000005 MBit/s is considered to be 0.
- The matrices are meant to be directed (just like the original data),
  that is, there might be traffic between s -> t and also t -> s.
- Loop traffic is already removed, that is, there is no demand between s <-> s

***********************
3. Format
***********************

For the new multiple demand matrix archives we decided to NOT introduce a new XML scheme
nor data format but to use the existing SNDlib formats.
This means that also all the available code (parsing/writing) can be used
for the multiple matrices.

A single demand matrix in the multiple matrices archive is just a Network object without a link section,
that is, it consists of nodes and demands between the nodes. It follows that the Network
parser/writer available in the SNDlib API can be used to parse/write a single demand matrix.
The node sections for all single matrices in the abilene archive are of course identical and
correspond to the abilene sndlib network.

In addition to a node and a demand section a single demand matrix also has a Meta-Section
giving additional information about the matrix such as the time stamp, the time horizon,
the origin, and the data unit. The new SNDlib API 1.3 is able to handle this (optional)
Meta-Section.


***********************
4. Remarks
***********************

We do not give any warranty for the correctness of the data.
There might be mistakes already in the original accounting data.
We might also have made mistakes in the creation of the data.

NOTICE: THERE ALWAYS IS ONE demandMatrix*.xml FOR EVERY MATRIX IN THE ORIGINAL DATA

NOTICE: There are gaps in the available information. For many points in time (days) there
        was no measurement available to us. In these cases we have not created a demand matrix:

          15.03.2004 ... 01.04.2004
          16.04.2004 ... 21.04.2004
          29.04.2004 ... 30.04.2004
          20.08.2004

        ... refers to any point in time in between


***********************
4. Original Abilene Readme
***********************

* Format of X*.gz

  Each file contains 12x24x7 = 2016 5-min traffic matrices.

  Unit: (100 bytes / 5 minutes)  // 100 is the pkt sampling rate

  Each line belongs to one TM; and each line contains 144x5=720 values
  organized as follows:

    <realOD_1> \
    <simpleGravityOD_1> \
    <simpleTomogravityOD_1> \
    <generalGravityOD_1> \
    <generalTomogravityOD_1> \

    ...

    <realOD_144> \
    <simpleGravityOD_144> \
    <simpleTomogravityOD_144> \
    <generalGravityOD_144> \
    <generalTomogravityOD_144> \

  where simpleGravity means the independence model: p(s,d) = p(s)p(d),
  whereas generalGravity means the conditional independence model,
  which treats outbound traffic differently.  simpleTomogravity and
  generalTomogravity are the tomogravity estimates with either
  simpleGravity or generalGravity as the prior.

  For Abilene, simpleGravity and generalGravity gives similar results.
  But in other networks, generalTomogravity often performs much
  better.

* Format of A

  A is the routing matrix.  it should be self-explanatory.

* Dates (the first day of each week)

  2004-03-01 X01
  2004-03-08 X02
  2004-04-02 X03
  2004-04-09 X04
  2004-04-22 X05
  2004-05-01 X06
  2004-05-08 X07
  2004-05-15 X08
  2004-05-22 X09
  2004-05-29 X10
  2004-06-05 X11
  2004-06-12 X12
  2004-06-19 X13
  2004-06-26 X14
  2004-07-03 X15
  2004-07-10 X16
  2004-07-17 X17
  2004-07-24 X18
  2004-07-31 X19
  2004-08-07 X20
  2004-08-13 X21
  2004-08-21 X22
  2004-08-28 X23
  2004-09-04 X24

* Collection methodology

  The idea is to directly work with destination AS numbers (which
  themselves are computed by the routers using the BGP tables when each
  netflow record is generated).

    (1) I examine the netflow leaving the egress links and build a set of
        destination AS numbers that egress at each router

    (2) from (1), for each destination AS number, I can find all the egress
        routers correspond to this AS.

    (3) At each ingress router, for each flow record, I can map its
        destination AS number to a set of egress routers using results
        of (2).  I then simulate OSPF to pick one egress router that is
        the closest.

  The above works as long as the destination AS is not Abilene (AS11537).

  When the destination is Abilene, in principle you could do the same
  thing on destination prefixes.  Unfortunately, the Abilene netflow
  mask out the last 11 bits of all the IP addresses, so it is impossible
  to get the true destination prefixes for Abilene.  As a result, the
  TMs I generated do not include any traffic destined for AS11537
  (fortunately they don't account for too much traffic).