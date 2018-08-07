import numpy as np
import nibabel as nb
import os
import sys
import cbstools
from ..io import load_volume, save_volume
from ..utils import _output_dir_4saving, _fname_4saving, \
                    _check_topology_lut_dir


def flash_t2s_fitting(image_list, te_list, 
                      save_data=False, overwrite=False, output_dir=None,
                      file_name=None):
    """ FLASH T2* fitting

    Estimate T2*/R2* by linear least squares fitting in log space. 

    Parameters
    ----------
    image_list: [niimg]
        List of input images to fit the T2* curve
    te_list: [float]
        List of input echo times (TE)
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
    dict
        Dictionary collecting outputs under the following keys
        (suffix of output files in brackets)

        * t2s (niimg): Map of estimated T2* times (_qt2fit-t2s)
        * r2s (niimg): Map of estimated R2* relaxation rate (_qt2fit-r2s)
        * s0 (niimg): Estimated PD weighted image at TE=0 (_qt2fit-s0)
        * residuals (niimg): Estimated residuals between input and estimated
        echoes (_qt2fit-err)

    Notes
    ----------
    Original Java module by Pierre-Louis Bazin.
    """

    print('\nT2* Fitting')

    # make sure that saving related parameters are correct
    if save_data:
        output_dir = _output_dir_4saving(output_dir, image_list[0])

        t2s_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                   rootfile=image_list[0],
                                   suffix='qt2fit-t2s'))

        r2s_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                   rootfile=image_list[0],
                                   suffix='qt2fit-r2s'))

        s0_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                   rootfile=image_list[0],
                                   suffix='qt2fit-s0'))

        err_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                   rootfile=image_list[0],
                                   suffix='qt2fit-err'))
        
        if overwrite is False \
            and os.path.isfile(t2s_file) \
            and os.path.isfile(r2s_file) \
            and os.path.isfile(s0_file) \
            and os.path.isfile(err_file) :
                print("skip computation (use existing results)")
                output = {'t2s': load_volume(t2s_file),
                          'r2s': load_volume(r2s_file), 
                          's0': load_volume(s0_file), 
                          'residuals': load_volume(err_file)}
                return output

    # start virtual machine, if not already running
    try:
        cbstools.initVM(initialheap='12000m', maxheap='12000m')
    except ValueError:
        pass
    # create algorithm instance
    qt2fit = cbstools.IntensityFlashT2sFitting()

    # set algorithm parameters
    qt2fit.setNumberOfEchoes(len(image_list))
     
    # load first image and use it to set dimensions and resolution
    img = load_volume(image_list[0])
    data = img.get_data()
    #data = data[0:10,0:10,0:10]
    affine = img.get_affine()
    header = img.get_header()
    resolution = [x.item() for x in header.get_zooms()]
    dimensions = data.shape

    qt2fit.setDimensions(dimensions[0], dimensions[1], dimensions[2])
    qt2fit.setResolutions(resolution[0], resolution[1], resolution[2])

    # input images
    # important: set image number before adding images
    for idx, image in enumerate(image_list):
        #print('\nloading ('+str(idx)+'): '+image)
        data = load_volume(image).get_data()
        #data = data[0:10,0:10,0:10]
        qt2fit.setEchoImageAt(idx, cbstools.JArray('float')(
                                    (data.flatten('F')).astype(float)))
    
    for idx, te in enumerate(te_list):
        qt2fit.setEchoTimeAt(idx, te)

    # execute the algorithm
    try:
        qt2fit.execute()

    except:
        # if the Java module fails, reraise the error it throws
        print("\n The underlying Java code did not execute cleanly: ")
        print(sys.exc_info()[0])
        raise
        return

    # reshape output to what nibabel likes
    t2s_data = np.reshape(np.array(qt2fit.getT2sImage(),
                                    dtype=np.float32), dimensions, 'F')

    r2s_data = np.reshape(np.array(qt2fit.getR2sImage(),
                                    dtype=np.float32), dimensions, 'F')

    s0_data = np.reshape(np.array(qt2fit.getS0Image(),
                                    dtype=np.float32), dimensions, 'F')

    err_data = np.reshape(np.array(qt2fit.getResidualImage(),
                                    dtype=np.float32), dimensions, 'F')

    # adapt header max for each image so that correct max is displayed
    # and create nifiti objects
    header['cal_min'] = np.nanmin(t2s_data)
    header['cal_max'] = np.nanmax(t2s_data)
    t2s = nb.Nifti1Image(t2s_data, affine, header)

    header['cal_min'] = np.nanmin(r2s_data)
    header['cal_max'] = np.nanmax(r2s_data)
    r2s = nb.Nifti1Image(r2s_data, affine, header)

    header['cal_min'] = np.nanmin(s0_data)
    header['cal_max'] = np.nanmax(s0_data)
    s0 = nb.Nifti1Image(s0_data, affine, header)

    header['cal_min'] = np.nanmin(err_data)
    header['cal_max'] = np.nanmax(err_data)
    err = nb.Nifti1Image(err_data, affine, header)

    if save_data:
        save_volume(t2s_file, t2s)
        save_volume(r2s_file, r2s)
        save_volume(s0_file, s0)
        save_volume(err_file, err)

    return {'t2s': t2s, 'r2s': r2s, 's0': s0, 'residuals': err}