.. _INSTALL:

====================================
Installation
====================================

The :ref:`scdummyloc<scdummyloc>` can integrate a standard :ref:`SeisComP compilation build env<https://github.com/SeisComP/seiscomp#seiscomp>`. But in its current form, one can install it most quickly by copying into the SeisComP root directory as follows.


.. code-block:: sh

   cp apps/scdummyloc/scdummyloc.py $SEISCOMP_ROOT/bin/scdummyloc
   chmod +x $SEISCOMP_ROOT/bin/scdummyloc
   cp apps/scdummyloc/initd.py $SEISCOMP_ROOT/etc/init/scdummyloc.py
   cp apps/scdummyloc/description/scdummyloc.xml $SEISCOMP_ROOT/etc/descriptions/
   cp apps/scdummyloc/config/scdummyloc.cfg $SEISCOMP_ROOT/etc/defaults/

