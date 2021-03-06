from nbodykit.core import DataSource
from nbodykit.utils import selectionlanguage
import numpy

class FOFDataSource(DataSource):
    """
    Class to read field data from a HDF5 FOFGroup data file

    Notes
    -----
    * `h5py` must be installed to use this data source.
    """
    plugin_name = "FOFGroups"
    
    def __init__(self, path, m0, dataset="FOFGroups", BoxSize=None, rsd=None, select=None):
        
        try:
            import h5py
        except:
            name = self.__class__.__name__
            raise ImportError("h5py must be installed to use '%s' reader" %name)

        
        self.path    = path
        self.m0      = m0
        self.dataset = dataset
        self.BoxSize = BoxSize
        self.rsd     = rsd
        self.select  = select
        
        BoxSize = numpy.empty(3, dtype='f8')
        if self.comm.rank == 0:
            self.logger.info("using %s : %s" % (self.path, self.dataset))
            try:
                dataset = h5py.File(self.path, mode='r')[self.dataset]
                BoxSize[:] = dataset.attrs['BoxSize']
                self.logger.info("Boxsize from file is %s" % str(BoxSize))
            except:
                self.logger.info("Boxsize not set in file")
                
        BoxSize = self.comm.bcast(BoxSize)

        if self.BoxSize is None:
            self.BoxSize = BoxSize
        else:
            if self.comm.rank == 0:
                self.logger.info("Overriding BoxSize as %s" % str(self.BoxSize))
        
    @classmethod
    def fill_schema(cls):
        s = cls.schema
        s.description = "read data from a HDF5 FOFGroup file"

        s.add_argument("path", type=str, help="the file path to load the data from")
        s.add_argument("m0", type=float, help="the mass unit")
        s.add_argument("dataset", type=str, help="the name of the dataset in HDF5 file")
        s.add_argument("BoxSize", type=cls.BoxSizeParser,
            help="overide the size of the box; can be a scalar or a three-vector")
        s.add_argument("rsd", type=str, choices="xyz", 
            help="direction to do redshift distortion")
        s.add_argument("select", type=selectionlanguage.Query, 
            help='row selection based on conditions specified as string')
    
    def readall(self):
        import h5py

        dataset = h5py.File(self.path, mode='r')[self.dataset]
        data = dataset[...]

        data2 = numpy.empty(len(data),
            dtype=[
                ('Position', ('f4', 3)),
                ('Velocity', ('f4', 3)),
                ('Mass', 'f4'),
                ('Weight', 'f4'),
                ('Length', 'i4'),
                ('Rank', 'i4'),
                ('LogMass', 'f4')])

        data2['Mass'] = data['Length'] * self.m0
        data2['Weight'] = 1.0
        data2['LogMass'] = numpy.log10(data2['Mass'])
        # get position and velocity, if we have it
        data2['Position'] = data['Position'] * self.BoxSize
        data2['Velocity'] = data['Velocity'] * self.BoxSize
        data2['Rank'] = numpy.arange(len(data))
        # select based on input conditions
        if self.select is not None:
            mask = self.select.get_mask(data2)
            data2 = data2[mask]

        nobj = (len(data2), len(data))

        self.logger.info("total number of objects selected is %d / %d" % nobj)

        if self.rsd is not None:
            dir = "xyz".index(self.rsd)
            data2['Position'][:, dir] += data2['Velocity'][:, dir]
            data2['Position'][:, dir] %= self.BoxSize[dir]

        return {key: data2[key].copy() for key in data2.dtype.names}

