*scdummyloc* is released under the GNU Affero General Public License (Free
Software Foundation, version 3 or later). It uses seismic phase onset picks for 
defining seismic event origins.

Pick association is solely based on simplistic thresholds:
- pick delay (see :confval:`max_pick_delay`) and 
- instrument location distance (see :confval:`max_pick_distance` and :confval:`min_pick_distance`).
   
Pick association supports picking from different instruments at the same station at the level of instrument location (see :confval:`enable_loc_clust`) code and channel code (:confval:`enable_cha_clust`). 

The preliminary origin locations are based on the average of picked instrument location (taking instrument elevation into account) weigthed by normalised arrival time (the earlier the closer to location).
 
.. note::

 *scdummyloc* is under developmnent.

Example for debugging (setup messaging parameters in :file:`scdummyloc.cfg`), origins are sent in messaging system, :ref:`scolv` for viewing and  :ref:`scmm` for inspection:

.. code-block:: sh

 scolv &
 scmm &
 scdummyloc --debug --fake -g GUI

Example for post-processing:

.. code-block:: sh

 scdummyloc --ep <pick file> --playback -d <database connection url> -o <output file> 
