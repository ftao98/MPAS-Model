#!/usr/bin/env python
import numpy
from netCDF4 import Dataset

from optparse import OptionParser

from progressbar import ProgressBar, Percentage, Bar, ETA

import os.path

import glob


def interpHoriz(field, inMask=None, outFraction=None):
    if inMask is not None:
        field = field*inMask
    outField = numpy.zeros((outNy,outNx))
    for sliceIndex in range(xyNSlices):
        mask = xySliceIndices == sliceIndex
        cellsSlice = xyCellIndices[mask]
        fieldSlice = field[cellsSlice]
        outField[xyYIndices[mask],xyXIndices[mask]] += (xyMpasToMisomipWeights[mask]
                * fieldSlice)
    if outFraction is not None:
        mask = outFraction > normalizationThreshold
        outField[mask] /= outFraction[mask]
        outField[numpy.logical_not(mask)] = 0.
    return outField


def interpHorizOcean(field):
    return interpHoriz(field, cellOceanMask, xyOceanFraction)

def interpHorizCavity(field):
    return interpHoriz(field, inCavityFraction, outCavityFraction)



def interpXZTransect(field, normalize=True):
    outField = numpy.zeros((outNz,outNx))

    for sliceIndex in range(xzNSlices):
        mask = xzSliceIndices == sliceIndex
        cellsSlice = xzCellIndices[mask]
        xIndices = xzXIndices[mask]
        weights = xzMpasToMisomipWeights[mask]
        for index in range(len(cellsSlice)):
            iCell = cellsSlice[index]
            xIndex = xIndices[index]
            weight = weights[index]
            layerThick = layerThickness[iCell,:]
            layerThick[maxLevelCell[iCell]+1:] = 0.
            zInterface = numpy.zeros(2*nVertLevels)
            fieldColumn = numpy.zeros(2*nVertLevels)
            fieldColumn[0::2] = field[iCell,:]
            fieldColumn[1::2] = field[iCell,:]
            zInterface[0] = ssh[iCell]
            zInterface[1::2] = ssh[iCell] - numpy.cumsum(layerThick[:])
            zInterface[2::2] = ssh[iCell] - numpy.cumsum(layerThick[:-1])
            outField[:,xIndex] += weight*numpy.interp(z, zInterface[::-1], fieldColumn[::-1],
                                                left=0., right=0.)

    if normalize:
        outField[xzOceanMask] /= xzOceanFraction[xzOceanMask]
        outField[xzOceanMask == False] = 0.

    return outField

def interpYZTransect(field, normalize=True):
    outField = numpy.zeros((outNz,outNy))

    for sliceIndex in range(yzNSlices):
        mask = yzSliceIndices == sliceIndex
        cellsSlice = yzCellIndices[mask]
        yIndices = yzYIndices[mask]
        weights = yzMpasToMisomipWeights[mask]
        for index in range(len(cellsSlice)):
            iCell = cellsSlice[index]
            yIndex = yIndices[index]
            weight = weights[index]
            layerThick = layerThickness[iCell,:]
            layerThick[maxLevelCell[iCell]+1:] = 0.
            zInterface = numpy.zeros(2*nVertLevels)
            fieldColumn = numpy.zeros(2*nVertLevels)
            fieldColumn[0::2] = field[iCell,:]
            fieldColumn[1::2] = field[iCell,:]
            zInterface[0] = ssh[iCell]
            zInterface[1::2] = ssh[iCell] - numpy.cumsum(layerThick[:])
            zInterface[2::2] = ssh[iCell] - numpy.cumsum(layerThick[:-1])
            outField[:,yIndex] += weight*numpy.interp(z, zInterface[::-1], fieldColumn[::-1],
                                                left=0., right=0.)

    if normalize:
        outField[yzOceanMask] /= yzOceanFraction[yzOceanMask]
        outField[yzOceanMask == False] = 0.

    return outField


def writeMetric(varName, metric):
    vars[varName][tIndex] = metric

def writeVar(varName, varField, varMask=None):
    if varMask is None:
        maskedVar = varField
    else:
        maskedVar = numpy.ma.masked_array(varField, mask=(varMask == False))
    vars[varName][tIndex, :, :] = maskedVar

parser = OptionParser()
           
options, args = parser.parse_args()

folder = args[0]
experiment = args[1]

inFileNames = sorted(glob.glob('%s/timeSeriesStatsMonthly.*.nc'%folder))

initFile = Dataset('{}/init.nc'.format(folder), 'r')
outFileName = '%s/%s_COM_MPAS-Ocean.nc'%(folder, experiment)

rho_fw = 1000.
secPerDay = 24*60*60
secPerYear = 365*secPerDay

normalizationThreshold = 0.001

outDx = 2e3
outX0 = 320e3
outY0 = 0.
outDz = 5.

outNx = 240
outNy = 40
outNz = 144

x = outX0 + outDx*(numpy.arange(outNx)+0.5)
y = outY0 + outDx*(numpy.arange(outNy)+0.5)
z = -outDz*(numpy.arange(outNz)+0.5)

inFile = Dataset('%s/intersections.nc'%folder,'r')
inVars = inFile.variables
xyCellIndices = inVars['cellIndices'][:]
xyXIndices = inVars['xIndices'][:]
xyYIndices = inVars['yIndices'][:]
xySliceIndices = inVars['sliceIndices'][:]
xyMpasToMisomipWeights = inVars['mpasToMisomipWeights'][:]
inFile.close()
xyNSlices = numpy.amax(xySliceIndices)+1

inFile = Dataset('%s/xTransectIntersections.nc'%folder,'r')
inVars = inFile.variables
yzCellIndices = inVars['cellIndices'][:]
yzYIndices = inVars['yIndices'][:]
yzSliceIndices = inVars['sliceIndices'][:]
yzMpasToMisomipWeights = inVars['mpasToMisomipWeights'][:]
inFile.close()
yzNSlices = numpy.amax(yzSliceIndices)+1

inFile = Dataset('%s/yTransectIntersections.nc'%folder,'r')
inVars = inFile.variables
xzCellIndices = inVars['cellIndices'][:]
xzXIndices = inVars['xIndices'][:]
xzSliceIndices = inVars['sliceIndices'][:]
xzMpasToMisomipWeights = inVars['mpasToMisomipWeights'][:]
inFile.close()
xzNSlices = numpy.amax(xzSliceIndices)+1

dynamicTopo = experiment in ['Ocean3', 'Ocean4', 'IceOcean1', 'IceOcean2']

initFile = Dataset('%s/init.nc'%folder,'r')
osfFile = Dataset('%s/overturningStreamfunction.nc'%folder,'r')
bsfFile = Dataset('%s/barotropicStreamfunction.nc'%folder,'r')
continueOutput = os.path.exists(outFileName)
if(continueOutput):
  outFile = Dataset(outFileName,'r+',format='NETCDF4')
  vars = outFile.variables
else:
  outFile = Dataset(outFileName,'w',format='NETCDF4')

  outFile.createDimension('nTime', None)
  outFile.createDimension('nx', outNx)
  outFile.createDimension('ny', outNy)
  outFile.createDimension('nz', outNz)

  for varName in ['x','y','z']:
    var = outFile.createVariable(varName,'f4',('n%s'%varName,))
    var.units = 'm'
    var.description = '%s location of cell centers'%varName
  vars = outFile.variables
  vars['x'][:] = x
  vars['y'][:] = y
  vars['z'][:] = z

  var = outFile.createVariable('time','f4',('nTime',))
  var.units = 's'
  var.description = 'time since start of simulation'

  var = outFile.createVariable('meanMeltRate','f4',('nTime'))
  var.units = 'm/s'
  var.description = 'mean melt rate averaged over area of floating ice, positive for melting'


  var = outFile.createVariable('totalMeltFlux','f4',('nTime'))
  var.units = 'kg/s'
  var.description = 'total flux of melt water summed over area of floating ice, positive for melting'

  var = outFile.createVariable('totalOceanVolume','f4',('nTime'))
  var.units = 'm^3'
  var.description = 'total volume of ocean'

  var = outFile.createVariable('meanTemperature','f4',('nTime'))
  var.units = 'deg C'
  var.description = 'the potential temperature averaged over the ocean volume'

  var = outFile.createVariable('meanSalinity','f4',('nTime'))
  var.units = 'PSU'
  var.description = 'the salinity averaged over the ocean volume'

  if dynamicTopo:
    outFile.createVariable('iceDraft','f4',('nTime','ny','nx',))
    outFile.createVariable('bathymetry','f4',('nTime','ny','nx',))
  else:
    outFile.createVariable('iceDraft','f4',('ny','nx',))
    outFile.createVariable('bathymetry','f4',('ny','nx',))

  var = vars['iceDraft']
  var.units = 'm'
  var.description = 'elevation of the ice-ocean interface'

  var = vars['bathymetry']
  var.units = 'm'
  var.description = 'elevation of the bathymetry'

  var = outFile.createVariable('meltRate','f4',('nTime','ny','nx',))
  var.units = 'm/s'
  var.description = 'melt rate, positive for melting'

  var = outFile.createVariable('frictionVelocity','f4',('nTime','ny','nx',))
  var.units = 'm/s'
  var.description = 'friction velocity u* used in melt calculations'

  var = outFile.createVariable('thermalDriving','f4',('nTime','ny','nx',))
  var.units = 'deg C'
  var.description = 'thermal driving used in the melt calculation'

  var = outFile.createVariable('halineDriving','f4',('nTime','ny','nx',))
  var.units = 'PSU'
  var.description = 'haline driving used in the melt calculation'

  var = outFile.createVariable('uBoundaryLayer','f4',('nTime','ny','nx',))
  var.units = 'm/s'
  var.description = 'x-velocity in the boundary layer used to compute u*'

  var = outFile.createVariable('vBoundaryLayer','f4',('nTime','ny','nx',))
  var.units = 'm/s'
  var.description = 'y-velocity in the boundary layer used to compute u*'

  var = outFile.createVariable('barotropicStreamfunction','f4',('nTime','ny','nx',))
  var.units = 'm^3/s'
  var.description = 'barotropic streamfunction'

  var = outFile.createVariable('overturningStreamfunction','f4',('nTime','nz','nx',))
  var.units = 'm^3/s'
  var.description = 'overturning (meridional) streamfunction'

  var = outFile.createVariable('bottomTemperature','f4',('nTime','ny','nx',))
  var.units = 'deg C'
  var.description = 'temperature in the bottom grid cell of each ocean column'

  var = outFile.createVariable('bottomSalinity','f4',('nTime','ny','nx',))
  var.units = 'PSU'
  var.description = 'salinity in the bottom grid cell of each ocean column'

  var = outFile.createVariable('temperatureXZ','f4',('nTime','nz','nx',))
  var.units = 'deg C'
  var.description = 'temperature slice in x-z plane through the center of the domain (y = 40 km)'

  var = outFile.createVariable('salinityXZ','f4',('nTime','nz','nx',))
  var.units = 'PSU'
  var.description = 'salinity slice in x-z plane through the center of the domain (y = 40 km)'

  var = outFile.createVariable('temperatureYZ','f4',('nTime','nz','ny',))
  var.units = 'deg C'
  var.description = 'temperature slice in y-z plane through x = 500 km'

  var = outFile.createVariable('salinityYZ','f4',('nTime','nz','ny',))
  var.units = 'PSU'
  var.description = 'salinity slice in y-z plane through x = 500 km'

nVertices = len(initFile.dimensions['nVertices'])
nCells = len(initFile.dimensions['nCells'])
nEdges = len(initFile.dimensions['nEdges'])
nVertLevels = len(initFile.dimensions['nVertLevels'])
nTimeIn = len(inFileNames)
nTimeIn = min(nTimeIn, len(bsfFile.dimensions['Time']))
nTimeIn = min(nTimeIn, len(osfFile.dimensions['nTime']))

if(continueOutput):
  nTimeOut = max(0, len(outFile.dimensions['nTime'])-2)
else:
  nTimeOut = 0

areaCell = initFile.variables['areaCell'][:]
bathymetry = -initFile.variables['bottomDepth'][:]
maxLevelCell = initFile.variables['maxLevelCell'][:]-1


cellMask = numpy.zeros((nCells, nVertLevels))
for iCell in range(nCells):
  k = maxLevelCell[iCell]
  if (k >= 0):
    cellMask[iCell,0:k+1] = 1.0

cellOceanMask = cellMask[:, 0]
xyOceanFraction = interpHoriz(cellOceanMask)
xyOceanMask = xyOceanFraction > normalizationThreshold

if not dynamicTopo and (nTimeOut == 0):
  vars['iceDraft'][:,:] = interpHorizOcean(initFile.variables['ssh'][0,:])
  vars['bathymetry'][:,:] = interpHorizOcean(bathymetry)

initFile.close()

daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
daysBeforeMonth = [0] + list(numpy.cumsum(daysInMonth))

pbar = ProgressBar(widgets=[Percentage(), Bar(), ETA()], maxval=nTimeIn).start()
for tIndex in range(nTimeOut, nTimeIn):
    inFile = Dataset(inFileNames[tIndex], 'r')
    inVars = inFile.variables
    days = 365*int(tIndex/12) + daysBeforeMonth[numpy.mod(tIndex, 12)]
    vars['time'][tIndex] = secPerDay*days

    freshwaterFlux = inVars['timeMonthly_avg_landIceFreshwaterFlux'][0, :]
    inCavityFraction = inVars['timeMonthly_avg_landIceFraction'][0, :]
    inCavityMask = inCavityFraction > normalizationThreshold
    outCavityFraction = interpHoriz(inCavityFraction)
    outCavityMask = outCavityFraction > normalizationThreshold
    meltRate = freshwaterFlux/rho_fw

    if not numpy.all(inCavityFraction == 0.):
        writeMetric('meanMeltRate', numpy.sum(meltRate*areaCell)
                                   /numpy.sum(inCavityFraction*areaCell))

    writeMetric('totalMeltFlux', numpy.sum(freshwaterFlux*areaCell))

    ssh = inVars['timeMonthly_avg_ssh'][0, :]
    columnThickness = ssh - bathymetry

    writeMetric('totalOceanVolume', numpy.sum(columnThickness*areaCell))

    thermalDriving = (inVars['timeMonthly_avg_landIceBoundaryLayerTracers_landIceBoundaryLayerTemperature'][0, :]
                    - inVars['timeMonthly_avg_landIceInterfaceTracers_landIceInterfaceTemperature'][0, :])
    halineDriving = (inVars['timeMonthly_avg_landIceBoundaryLayerTracers_landIceBoundaryLayerSalinity'][0, :]
                   - inVars['timeMonthly_avg_landIceInterfaceTracers_landIceInterfaceSalinity'][0, :])
    frictionVelocity = inVars['timeMonthly_avg_landIceFrictionVelocity'][0, :]

    bsfCell = 1e6*bsfFile.variables['barotropicStreamfunctionCell'][tIndex, :]

    # meltRate is already multiplied by inCavityFraction, so no in masking
    writeVar('meltRate',
             interpHoriz(meltRate, inMask=None, outFraction=outCavityFraction),
             outCavityMask)
    writeVar('thermalDriving', interpHorizCavity(thermalDriving), outCavityMask)
    writeVar('halineDriving', interpHorizCavity(halineDriving), outCavityMask)
    writeVar('frictionVelocity', interpHorizCavity(frictionVelocity),
             outCavityMask)
    writeVar('barotropicStreamfunction', interpHorizOcean(bsfCell),
             xyOceanMask)

    temperature = inVars['timeMonthly_avg_activeTracers_temperature'][0, :,:]
    salinity = inVars['timeMonthly_avg_activeTracers_salinity'][0, :,:]
    layerThickness = inVars['timeMonthly_avg_layerThickness'][0, :,:]

    indices = numpy.arange(nCells)
    bottomTemperature = temperature[indices, maxLevelCell]
    bottomSalinity = salinity[indices, maxLevelCell]

    writeVar('bottomTemperature', interpHorizOcean(bottomTemperature),
             xyOceanMask)
    writeVar('bottomSalinity', interpHorizOcean(bottomSalinity),
             xyOceanMask)

    writeMetric('meanTemperature', numpy.sum(cellMask*layerThickness*temperature)
                                  /numpy.sum(cellMask*layerThickness))
    writeMetric('meanSalinity', numpy.sum(cellMask*layerThickness*salinity)
                               /numpy.sum(cellMask*layerThickness))

    uTop = inVars['timeMonthly_avg_velocityX'][0, :, 0]
    vTop = inVars['timeMonthly_avg_velocityY'][0, :, 0]
    writeVar('uBoundaryLayer', interpHorizCavity(uTop), outCavityMask)
    writeVar('vBoundaryLayer', interpHorizCavity(vTop), outCavityMask)

    osf = 1e6*osfFile.variables['overturningStreamfunction'][tIndex, :, :]
    osfX = osfFile.variables['x'][:]
    osfZ = osfFile.variables['z'][:]
    assert(numpy.all(osfX == x))
    assert(numpy.all(osfZ == z))
    
    writeVar('overturningStreamfunction', osf)
  
    xzOceanFraction = interpXZTransect(cellMask, normalize=False)
    xzOceanMask = xzOceanFraction > 0.001

    yzOceanFraction = interpYZTransect(cellMask, normalize=False)
    yzOceanMask = yzOceanFraction > 0.001

    writeVar('temperatureXZ', interpXZTransect(temperature), xzOceanMask)
    writeVar('salinityXZ', interpXZTransect(salinity), xzOceanMask)
  
    writeVar('temperatureYZ', interpYZTransect(temperature), yzOceanMask)
    writeVar('salinityYZ', interpYZTransect(salinity), yzOceanMask)
    pbar.update(tIndex+1)

pbar.finish()

outFile.close()
osfFile.close()
bsfFile.close()

