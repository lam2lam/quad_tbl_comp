This project is to develop table compression algorithm with O(1) (random access) capability
There are coefficients gerneated by Maple, the intention is to approximate elementary functions using quadratic equations
The target equations are log2, pow2, recp (1/x), sqrt (but there are 2 sections, 1_to_2 and 2_to_4), rsqrt (1/sqrt(x), and just like sqrt, there are 2 sections too), they're in .txt format in the current folder
So there are 7 tables in total
The files all contains a header, but they are irrelavent to our project here, all data starts after the "------" separator line
There are 3 columns on each row, they would be called C0/C1/C2 respective.  Each row corresponds to the lut's index, C0[0] was the first number on the first row after the separator, C1[0] was the second number, C2[0] was the thrid number
C0 should be 26 bits, C1 16 bits, and C2 was 10 bits.  All of the numbers are hex format, and they are all unsigned numbers

One of the algorithm (provided by google) was to compress the table using "diff of diffs".  e.g. C0[0] was first stored, and C0[1]-C0[0] was then stored.  Finally, (C0[i+1]-C0[i]) - (C0[i]-C0[i-1]) was stored.  But this algorithm obviously cannot be O(1), instead it's O(n).  But this is basically you can consider this as the "best" case you can get. <- build a script to compute the best possible
When calculting "cost", you can count the number of bits required as ceil(log2(max(C0))) + ceil(log2(max(C1))) + ceil(log2(max(C2))), and then resulting compressed form as ceil(log2(C0[0])) + ceil(log2(abs(C0[1]-C0[0]))) + ceil(log2(abs(max(C0[i+1]-2*C0[i]+C0[i-1])))), same for C1 and C2, not repeated.  ** abs was here because the delta could be negative.  You can, further partitioning the compressed table, e.g. I can imagine that, the diffs would be smaller and smaller (or larger and larger), that by sub-partitioning it can save a few more bits if the table have all the msbs the same.  But, to be realistic on the segments, the segments should be 2^N, and at least each segment should contain 8 numbers

Now to be realistic on the O(1), another proposal was made, that we segments each column as groups of 4 numbers
e.g. C0[0] was stored in full, and then C0[1] - C0[0] was stored in diff.  And then C0[2] - 2*C0[1] + C0[0] (diff[2->1] - diff[1->0]) and C0[3] - 2*C0[1] + C0[0] (diff[3->1] - diff[1->0]) was stored.  in other words, we store the full number for all index 4*i, diff for all index 4*i+1 (this would require an adder) diff of diff for 4*i+{2,3} (this would require 2 adders in series).  <- build a script to compute this too.  
You can, also make use of the segmentation method, for example, C0[4*i] sequence contains a "flatter" region, less bits was necessary, you can always segment that too.  But the least segment group should still be observed, since 64 (or 128) already / 4, there are at most 2 to 4 groups segmented for each column of each table.

Another algorithm was proposed, was that we group each column in group of G, we would first find a line, in the form a mx+b that passes the group of G numbers (such that x takes the range from 0 to G-1), which minimize the max error (note not total error, just the max error determines our table size), and then stores also the difference against the mx+b line.  G should be 2^N, and can try like G=2,4,8 (otherwise the number of adders will increase..)  <- build a script to compute this too.  The segmentation method could be applied also

Please, after any of the above scripts, always run an regression that make sure the tables could be reproduced.  
