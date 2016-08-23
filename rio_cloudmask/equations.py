#!/usr/bin/env python
# coding: utf8
from __future__ import division

import numpy as np


def basic_test(ndvi, ndsi, swir2, tirs1):
    """Fundamental test to identify Potential Cloud Pixels (PCPs)

    Equation 1 (Zhu and Woodcock, 2012)

    Note: all input arrays must be the same shape

    Parameters
    ----------
    ndvi: ndarray
    ndsi: ndarray
    swir2: ndarray
        Shortwave Infrared Band TOA reflectance
        Band 7 in Landsat 8, ~2.2 µm
    tirs1: ndarray
        Thermal band brightness temperature
        Band 10 in Landsat 8, ~11 µm
        units are degrees Celcius

    Output
    ------
    ndarray: boolean
    """
    # Thresholds
    th_ndsi = 0.8  # index
    th_ndvi = 0.8  # index
    th_tirs1 = 27.0  # degrees celcius
    th_swir2 = 0.03  # toa

    return ((swir2 > th_swir2) &
            (tirs1 < th_tirs1) &
            (ndsi < th_ndsi) &
            (ndvi < th_ndvi))


def whiteness_index(blue, green, red):
    """Index of "Whiteness" based on visible bands.

    Parameters
    ----------
    blue: ndarray
    green: ndarray
    red: ndarray

    Output
    ------
    ndarray:
        whiteness index
    """
    mean_vis = (blue + green + red) / 3

    blue_absdiff = np.absolute((blue - mean_vis) / mean_vis)
    green_absdiff = np.absolute((green - mean_vis) / mean_vis)
    red_absdiff = np.absolute((red - mean_vis) / mean_vis)

    return blue_absdiff + green_absdiff + red_absdiff


def whiteness_test(blue, green, red):
    """Whiteness test
    Clouds appear white due to their "flat" reflectance in the visible bands

    Equation 2 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    blue: ndarray
    green: ndarray
    red: ndarray

    Output
    ------
    ndarray: boolean
    """
    whiteness_threshold = 0.7
    return whiteness_index(blue, green, red) < whiteness_threshold


def hot_test(blue, red):
    """Haze Optimized Transformation (HOT) test

    Equation 3 (Zhu and Woodcock, 2012)

    Based on the premise that the visible bands for most land surfaces
    are highly correlated, but the spectral response to haze and thin cloud
    is different between the blue and red wavelengths.
    Zhang et al. (2002)

    Parameters
    ----------
    blue: ndarray
    red: ndarray

    Output
    ------
    ndarray: boolean
    """
    thres = 0.08
    return blue - (0.5 * red) - thres > 0.0


def nirswir_test(nir, swir1):
    """Spectral test to exclude bright rock and desert
    see (Irish, 2000)

    Equation 4 (Zhu and Woodcock, 2012)

    Note that Zhu and Woodcock 2015 refer to this as the "B4B5" test
    due to the Landsat ETM+ band designations. In Landsat 8 OLI,
    these are bands 5 and 6.

    Parameters
    ----------
    nir: ndarray
    swir1: ndarray

    Output
    ------
    ndarray: boolean
    """
    th_ratio = 0.75

    return (nir / swir1) > th_ratio


def cirrus_test(cirrus):
    """Cirrus TOA test, see (Zhu and Woodcock, 2015)

    The threshold is derived from (Wilson & Oreopoulos, 2013)

    Parameters
    ----------
    cirrus: ndarray

    Output
    ------
    ndarray: boolean
    """
    th_cirrus = 0.01

    return cirrus > th_cirrus


def water_test(ndvi, nir):
    """Water or Land?

    Equation 5 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    ndvi: ndarray
    nir: ndarray

    Output
    ------
    ndarray: boolean
    """
    th_ndvi_A = 0.01
    th_nir_A = 0.11
    th_ndvi_B = 0.1
    th_nir_B = 0.05

    return (((ndvi < th_ndvi_A) & (nir < th_nir_A)) |
            ((ndvi < th_ndvi_B) & (nir < th_nir_B)))


def potential_cloud_pixels(ndvi, ndsi, blue, green, red, nir,
                           swir1, swir2, cirrus, tirs1):
    """Determine potential cloud pixels (PCPs)
    Combine basic spectral tests to get a premliminary cloud mask
    First pass, section 3.1.1 in Zhu and Woodcock 2012

    Equation 6 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    ndvi: ndarray
    ndsi: ndarray
    blue: ndarray
    green: ndarray
    red: ndarray
    nir: ndarray
    swir1: ndarray
    swir2: ndarray
    cirrus: ndarray
    tirs1: ndarray

    Output
    ------
    ndarray:
        potential cloud mask, boolean
    """
    eq1 = basic_test(ndvi, ndsi, swir2, tirs1)
    eq2 = whiteness_test(blue, green, red)
    eq3 = hot_test(blue, red)
    eq4 = nirswir_test(nir, swir1)
    cir = cirrus_test(cirrus)

    return (eq1 & eq2 & eq3 & eq4) | cir


def temp_water(is_water, swir2, tirs1):
    """Use water to mask tirs and find 82.5 pctile

    Equation 7 and 8 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    is_water: ndarray, boolean
        water mask, water is True, land is False
    swir2: ndarray
    tirs1: ndarray

    Output
    ------
    float:
        82.5th percentile temperature over water
    """
    # eq7
    th_swir2 = 0.03
    clearsky_water = is_water & (swir2 < th_swir2)

    # eq8
    clear_water_temp = tirs1.copy()
    clear_water_temp[~clearsky_water] = np.nan
    return np.nanpercentile(clear_water_temp, 82.5)


def water_temp_prob(water_temp, tirs):
    """Temperature probability for water

    Equation 9 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    water_temp: float
        82.5th percentile temperature over water
    swir2: ndarray
    tirs1: ndarray

    Output
    ------
    ndarray:
        probability of cloud over water based on temperature
    """
    temp_const = 4.0  # degrees C
    return (water_temp - tirs) / temp_const


def brightness_prob(nir):
    """The brightest water may have Band 5 reflectance
    as high as 0.11

    Equation 10 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    nir: ndarray

    Output
    ------
    ndarray:
        brightness probability
    """
    thresh = 0.11
    return np.minimum(thresh, nir) / thresh


# Eq 11, water_cloud_prob
# wCloud_Prob = wTemperature_Prob x Brightness_Prob


def temp_land(pcps, water, tirs1):
    """Derive high/low percentiles of land temperature

    Equations 12 an 13 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    pcps: ndarray
        potential cloud pixels, boolean
    water: ndarray
        water mask, boolean
    tirs1: ndarray

    Output
    ------
    tuple:
        17.5 and 82.5 percentile temperature over clearsky land
    """
    # eq 12
    clearsky_land = ~(pcps | water)

    # use clearsky_land to mask tirs1
    clear_land_temp = tirs1.copy()
    clear_land_temp[~clearsky_land] = np.nan

    # take 17.5 and 82.5 percentile, eq 13
    return np.nanpercentile(clear_land_temp, (17.5, 82.5))


def land_temp_prob(tirs1, tlow, thigh):
    """Temperature-based probability of cloud over land

    Equation 14 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    tirs1: ndarray
    tlow: float
        Low (17.5 percentile) temperature of land
    thigh: float
        High (82.5 percentile) temperature of land

    Output
    ------
    ndarray :
        probability of cloud over land based on temperature
    """
    temp_diff = 4  # degrees
    return (thigh + temp_diff - tirs1) / (thigh + 4 - (tlow - 4))


def variability_prob(ndvi, ndsi, whiteness):
    """Use the probability of the spectral variability
    to identify clouds over land.

    Equation 15 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    ndvi: ndarray
    ndsi: ndarray
    whiteness: ndarray

    Output
    ------
    ndarray :
        probability of cloud over land based on variability
    """
    return 1.0 - np.fmax(np.absolute(ndvi), np.absolute(ndsi), whiteness)


# Eq 16, land_cloud_prob
# lCloud_Prob = lTemperature_Prob x Variability_Prob


def land_threshold(land_cloud_prob, pcps, water):
    """Dynamic threshold for determining cloud cutoff

    Equation 17 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    land_cloud_prob: ndarray
        probability of cloud over land
    pcps: ndarray
        potential cloud pixels
    water: ndarray
        water mask

    Output
    ------
    float:
        land cloud threshold
    """
    # eq 12
    clearsky_land = ~(pcps | water)

    # 82.5th percentile of lCloud_Prob(masked by clearsky_land) + 0.2
    cloud_prob = land_cloud_prob.copy()
    cloud_prob[~clearsky_land] = np.nan

    # eq 17
    th_const = 0.2
    return np.nanpercentile(cloud_prob, 82.5) + th_const


def potential_cloud_layer(pcp, water, tirs1, tlow,
                          land_cloud_prob, land_threshold,
                          water_cloud_prob, water_threshold=0.5):
    """Final step of determining potential cloud layer

    Equation 18 (Zhu and Woodcock, 2012)

    Parameters
    ----------
    pcps: ndarray
        potential cloud pixels
    water: ndarray
        water mask
    tirs1: ndarray
    tlow: float
        low percentile of land temperature
    land_cloud_prob: ndarray
        probability of cloud over land
    land_threshold: float
        cutoff for cloud over land
    water_cloud_prob: ndarray
        probability of cloud over water
    water_threshold: float
        cutoff for cloud over water

    Output
    ------
    ndarray:
        potential cloud layer, boolean
    """
    # Using pcp and water as mask todo
    part1 = (pcp & water & (water_cloud_prob > water_threshold))
    part2 = (pcp & ~water & (land_cloud_prob > land_threshold))
    temptest = tirs1 < (tlow - 35)  # 35degrees C colder

    return part1 | part2 | temptest


def calc_ndsi(green, swir1):
    """NDSI calculation
    normalized difference snow index

    Parameters
    ----------
    green: ndarray
    swir1: ndarray
        ~1.62 µm
        Band 6 in Landsat 8

    Output
    ------
    ndarray:
        unitless index
    """
    return (green - swir1) / (green + swir1)


def calc_ndvi(red, nir):
    """NDVI calculation
    normalized difference vegetation index

    Parameters
    ----------
    red: ndarray
    nir: ndarray

    Output
    ------
    ndarray:
        unitless index
    """
    return (nir - red) / (nir + red)


def cloudmask(blue, green, red, nir, swir1, swir2,
              cirrus, tirs1, run_filter=True):
    """Calculate the potential cloud layer from source data

    *This is the high level function which ties together all
    the equations for generating potential clouds*

    Parameters
    ----------
    blue: ndarray
    green: ndarray
    red: ndarray
    nir: ndarray
    swir1: ndarray
    swir2: ndarray
    cirrus: ndarray
    tirs1: ndarray
    run_filter: boolean
        Run scipy filters to remove outliers and smooth edges?

    Output
    ------
    ndarray, uint8:
        0 = cloud, 255 = clear sky
    """
    ndvi = calc_ndvi(red, nir)
    ndsi = calc_ndvi(green, swir1)
    whiteness = whiteness_index(blue, green, red)
    water = water_test(ndvi, nir)

    # First pass, potential clouds
    pcps = potential_cloud_pixels(
        ndvi, ndsi, blue, green, red, nir, swir1, swir2, cirrus, tirs1)

    # Clouds over water
    tw = temp_water(water, swir2, tirs1)
    wtp = water_temp_prob(tw, tirs1)
    bp = brightness_prob(nir)
    water_cloud_prob = wtp * bp
    wthreshold = 0.5

    # Clouds over land
    tlow, thigh = temp_land(pcps, water, tirs1)
    ltp = land_temp_prob(tirs1, tlow, thigh)
    vp = variability_prob(ndvi, ndsi, whiteness)
    land_cloud_prob = ltp * vp
    lthreshold = land_threshold(land_cloud_prob, pcps, water)

    pcl = potential_cloud_layer(
        pcps, water, tirs1, tlow,
        land_cloud_prob, lthreshold,
        water_cloud_prob, wthreshold)

    if run_filter:
        from scipy.ndimage.filters import median_filter, maximum_filter

        # smooth outliers
        pcl = median_filter(pcl, size=(9, 9))

        # grow around the edges
        pcl = maximum_filter(pcl, size=(13, 13))

    return (~pcl * 255).astype('uint8')  # gdal-style