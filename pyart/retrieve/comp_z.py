"""
Calculate the composite reflectivity 

"""

import copy
import numpy as np
from netCDF4 import num2date
from pandas import to_datetime


def upsample(x):
    x_new = np.kron(x, np.ones((2,1)))
    return x_new 

def composite_reflectivity(radar,rhv_filter=True,rhv_value=0.95,verbose=False):
    
    """
    Composite Reflectivity 
    
    Often a legacy product, composite reflectivity is: 
    "A display or mapping of the maximum radar reflectivity factor at any altitude as a function of position on the ground." - AMS Glossary 
    
    This is more useful for the dry regions of the world, where maximum reflectivity values are found aloft, as opposed to the lowest
    scan. Alternatively this is useful for comparing to NWP since composite Z is a standard output of NWP. 


    Why this is not as easy as one would think: Turns out the data are not natively stored with index 0 being azimuth 0. Likely due
    to the physical spinning of the radar antenna. 
    
    Author: Randy J. Chase (@dopplerchase) 
    
    Note: this function could potenially be parallelized at the loop, but for now runs in ~5 seconds on my 16 GB Mac
    
    Parameters
    ----------
    radar : Radar
        Radar object used.
    rhv_filter : bool
        boolean flag to turn on correlation coef. filtering. 
    rhv_value : float
        value to consider 'meteorological'
    verbose : bool
        boolean flag to turn the printing of radar tilts on or off. 

    Returns
    -------
    comp_dict : Dictonary
        A dictionary containing the sorted lon,lat grid and the composite reflectivity value
        This will be [azimuth,range]
        
    """
    
    #loop over all measured sweeps 
    for sweep in radar.sweep_number['data']:
    
        #get start and stop index numbers
        s_idx = radar.sweep_start_ray_index['data'][sweep]
        e_idx = radar.sweep_end_ray_index['data'][sweep]+1
        
        #grab radar data 
        z = radar.get_field(sweep,'reflectivity')
        
        #filter out values if desired. Future we should use gate filters...
        if rhv_filter:
            rho_hv = radar.get_field(sweep,'cross_correlation_ratio')
            z = np.ma.masked_where(rho_hv < rhv_value, z)

        #extract lat lons 
        lon = radar.gate_longitude['data'][s_idx:e_idx,:]
        lat = radar.gate_latitude['data'][s_idx:e_idx,:]

        #get azimuth
        az = radar.azimuth['data'][s_idx:e_idx]
        #get order of azimuths 
        az_ids = np.argsort(az)

        #reorder azs so they are in order 
        z = z[az_ids]
        lon = lon[az_ids]
        lat = lat[az_ids]
        
        #if the first sweep, store re-ordered lons/lats
        if sweep == 0:
            lon_0 = copy.deepcopy(lon)
            lon_0[-1,:] = lon_0[0,:]
            lat_0 = copy.deepcopy(lat)
            lat_0[-1,:] = lat_0[0,:]
        
        #if 360 scan, upsample to super res
        if lon.shape[0] < 720:
            z = upsample(z)
        
        #if first sweep, create new dim, otherwise concat them up 
        if sweep == 0:
            z_stack = copy.deepcopy(z[np.newaxis,:,:])
        else:
            z_stack = np.concatenate([z_stack,z[np.newaxis,:,:]])
            
    #now that the stack is made, take max across vertical 
    compz = z_stack.max(axis=0)
    
    #since we are using the whole volume scan, report mean time 
    dtime = to_datetime(num2date(radar.time['data'],radar.time['units']).astype(str))
    dtime = dtime.mean()
    
    #return dict, because this is was pyart does with lots of things 
    comp_dict = {}
    comp_dict['longitude'] = {'data':lon_0,'units':'degrees','info':'reordered longitude grid, [az,range]'}
    comp_dict['latitude'] = {'data':lat_0,'units':'degrees','info':'reordered latitude grid, [az,range]'}
    comp_dict['composite_reflectivity']= {'data':compz,'units':'dBZ','info':'composite refelctivity computed from calculating the max radar value in each radar gate vertically after reordering'}
    comp_dict['time'] = {'data':dtime,'units':'timestamp','info':'mean time of all scans'}
    return comp_dict