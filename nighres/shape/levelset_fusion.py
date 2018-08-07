import os
import numpy as np
import nibabel as nb
import cbstools
from ..io import load_volume, save_volume
from ..utils import _output_dir_4saving, _fname_4saving, \
                    _check_topology_lut_dir


def levelset_fusion(levelset_images,
                    correct_topology=True, topology_lut_dir=None,
                    save_data=False, overwrite=False, output_dir=None,
                    file_name=None):

    """Levelset fusion

    Creates an average levelset surface representations from a collection of 
    levelset surfaces, with same avearage volume and (opftionally) spherical topology

    Parameters
    ----------
    levelset_images: [niimg]
        List of levelset images to combine.
    correct_topology: bool
        Corrects the average shape to ensure correct topology (default is True)
    topology_lut_dir: str
        Path to directory in which topology files are stored (default is stored
        in TOPOLOGY_LUT_DIR)
    save_data: bool
        Save output data to file (default is False)
    overwrite: bool
        Overwrite existing results (default is False)
    output_dir: str, optional
        Path to desired output directory, will be created if it doesn't exist
    file_name: str, optional
        Desired base name for output files with file extension
        (suffixes will be added)

    Returns
    ----------
    niimg
        Levelset representation of combined surface (output file suffix _lsf_avg)

    Notes
    ----------
    Original Java module by Pierre-Louis Bazin
    """

    print("\nLevelset Shape Fusion")

    # check topology_lut_dir and set default if not given
    topology_lut_dir = _check_topology_lut_dir(topology_lut_dir)

    # make sure that saving related parameters are correct
    if save_data:
        output_dir = _output_dir_4saving(output_dir, levelset_images[0])

        levelset_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                       rootfile=levelset_images[0],
                                       suffix='lsf-avg'))
        print('output file: '+levelset_file)
        if overwrite is False \
            and os.path.isfile(levelset_file) :
            
            print("skip computation (use existing results)")
            output = {'result': load_volume(levelset_file)}
            return output

    # start virtual machine if not running
    try:
        cbstools.initVM(initialheap='6000m', maxheap='6000m')
    except ValueError:
        pass

    # initiate class
    algorithm = cbstools.ShapeLevelsetFusion()

    # load the data
    nsubjects = len(levelset_images)
    
    img = load_volume(levelset_images[0])
    hdr = img.get_header()
    aff = img.get_affine()
    resolution = [x.item() for x in hdr.get_zooms()]
    dimensions = img.get_data().shape
    
    algorithm.setNumberOfImages(nsubjects)
    algorithm.setResolutions(resolution[0], resolution[1], resolution[2])
    algorithm.setDimensions(dimensions[0], dimensions[1], dimensions[2])

    levelset_data = [];
    for idx in range(len(levelset_images)):
        img = load_volume(levelset_images[idx])
        data = img.get_data()
        algorithm.setLevelsetImageAt(idx, cbstools.JArray('float')(
                                            (data.flatten('F')).astype(float)))
    
    algorithm.setCorrectSkeletonTopology(correct_topology)
    algorithm.setTopologyLUTdirectory(topology_lut_dir)
    
    # execute class
    try:
        algorithm.execute()

    except:
        # if the Java module fails, reraise the error it throws
        print("\n The underlying Java code did not execute cleanly: ")
        print(sys.exc_info()[0])
        raise
        return

    # collect outputs
    levelset_data = np.reshape(np.array(algorithm.getLevelsetAverage(),
                               dtype=np.float32), dimensions, 'F')

    hdr['cal_min'] = np.nanmin(levelset_data)
    hdr['cal_max'] = np.nanmax(levelset_data)
    levelset = nb.Nifti1Image(levelset_data, aff, hdr)

    if save_data:
        save_volume(levelset_file, levelset)

    return {'result': levelset}
