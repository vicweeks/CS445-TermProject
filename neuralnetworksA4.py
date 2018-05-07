import numpy as np
import mlutilities as ml
import pickle
from copy import copy
import time
import sys

######################################################################
##  class NeuralNetwork
######################################################################

class NeuralNetwork:

    def __init__(self, ni, nhs, no):
        if isinstance(nhs, list) or isinstance(nhs, tuple):
            nihs = [ni] + list(nhs)
        else:
            if nhs > 0:
                nihs = [ni, nhs]
                nhs = [nhs]
            else:
                nihs = [ni]
                nhs = []
        if len(nihs) > 1:
            self.Vs = [1/np.sqrt(nihs[i]) *
                       np.random.uniform(-1, 1, size=(1+nihs[i], nihs[i+1])) for i in range(len(nihs)-1)]
            self.W = 1/np.sqrt(nhs[-1]) * np.random.uniform(-1, 1, size=(1+nhs[-1], no))
        else:
            self.Vs = []
            self.W = 1/np.sqrt(ni) * np.random.uniform(-1, 1, size=(1+ni, no))
        self.ni, self.nhs, self.no = ni, nhs, no
        self.Xmeans = None
        self.Xstds = None
        self.Tmeans = None
        self.Tstds = None
        self.trained = False
        self.reason = None
        self.errorTrace = None
        self.numberOfIterations = None
        self.trainingTime = None

    def __repr__(self):
        str = 'NeuralNetwork({}, {}, {})'.format(self.ni, self.nhs, self.no)
        # str += '  Standardization parameters' + (' not' if self.Xmeans == None else '') + ' calculated.'
        if self.trained:
            str += '\n   Network was trained for {} iterations that took {:.4f} seconds. Final error is {}.'.format(self.numberOfIterations, self.getTrainingTime(), self.errorTrace[-1])
        else:
            str += '  Network is not trained.'
        return str

    def _standardizeX(self, X):
        result = (X - self.Xmeans) / self.XstdsFixed
        result[:, self.Xconstant] = 0.0
        return result

    def _unstandardizeX(self, Xs):
        return self.Xstds * Xs + self.Xmeans

    def _standardizeT(self, T):
        result = (T - self.Tmeans) / self.TstdsFixed
        result[:, self.Tconstant] = 0.0
        return result

    def _unstandardizeT(self, Ts):
        return self.Tstds * Ts + self.Tmeans

    def _pack(self, Vs, W):
        return np.hstack([V.flat for V in Vs] + [W.flat])

    def _unpack(self, w):
        first = 0
        numInThisLayer = self.ni
        for i in range(len(self.Vs)):
            self.Vs[i][:] = w[first:first+(numInThisLayer+1)*self.nhs[i]].reshape((numInThisLayer+1, self.nhs[i]))
            first += (numInThisLayer+1) * self.nhs[i]
            numInThisLayer = self.nhs[i]
        self.W[:] = w[first:].reshape((numInThisLayer+1, self.no))

    def _objectiveF(self, w, X, T):
        self._unpack(w)
        # Do forward pass through all layers
        Zprev = X
        for i in range(len(self.nhs)):
            V = self.Vs[i]
            Zprev = np.tanh(Zprev @ V[1:, :] + V[0:1, :])  # handling bias weight without adding column of 1's
        Y = Zprev @ self.W[1:, :] + self.W[0:1, :]
        return 0.5 * np.mean((T-Y)**2)

    def _gradientF(self, w, X, T):
        self._unpack(w)
        # Do forward pass through all layers
        Zprev = X
        Z = [Zprev]
        for i in range(len(self.nhs)):
            V = self.Vs[i]
            Zprev = np.tanh(Zprev @ V[1:, :] + V[0:1, :])
            Z.append(Zprev)
        Y = Zprev @ self.W[1:, :] + self.W[0:1, :]
        # Do backward pass, starting with delta in output layer
        delta = -(T - Y) / (X.shape[0] * T.shape[1])
        dW = np.vstack((np.ones((1, delta.shape[0])) @ delta, 
                        Z[-1].T @ delta))
        dVs = []
        delta = (1 - Z[-1]**2) * (delta @ self.W[1:, :].T)
        for Zi in range(len(self.nhs), 0, -1):
            Vi = Zi - 1  # because X is first element of Z
            dV = np.vstack((np.ones((1, delta.shape[0])) @ delta,
                            Z[Zi-1].T @ delta))
            dVs.insert(0, dV)
            delta = (delta @ self.Vs[Vi][1:, :].T) * (1 - Z[Zi-1]**2)
        return self._pack(dVs, dW)

    def train(self, X, T, nIterations=100, verbose=False,
              weightPrecision=0, errorPrecision=0, saveWeightsHistory=False):
        
        if self.Xmeans is None:
            self.Xmeans = X.mean(axis=0)
            self.Xstds = X.std(axis=0)
            self.Xconstant = self.Xstds == 0
            self.XstdsFixed = copy(self.Xstds)
            self.XstdsFixed[self.Xconstant] = 1
        X = self._standardizeX(X)

        if T.ndim == 1:
            T = T.reshape((-1, 1))

        if self.Tmeans is None:
            self.Tmeans = T.mean(axis=0)
            self.Tstds = T.std(axis=0)
            self.Tconstant = self.Tstds == 0
            self.TstdsFixed = copy(self.Tstds)
            self.TstdsFixed[self.Tconstant] = 1
        T = self._standardizeT(T)

        startTime = time.time()

        scgresult = ml.scg(self._pack(self.Vs, self.W),
                            self._objectiveF, self._gradientF,
                            X, T,
                            xPrecision=weightPrecision,
                            fPrecision=errorPrecision,
                            nIterations=nIterations,
                            verbose=verbose,
                            ftracep=True,
                            xtracep=saveWeightsHistory)

        self._unpack(scgresult['x'])
        self.reason = scgresult['reason']
        self.errorTrace = np.sqrt(scgresult['ftrace']) # * self.Tstds # to _unstandardize the MSEs
        self.numberOfIterations = len(self.errorTrace)
        self.trained = True
        self.weightsHistory = scgresult['xtrace'] if saveWeightsHistory else None
        self.trainingTime = time.time() - startTime
        return self

    def use(self, X, allOutputs=False):
        Zprev = self._standardizeX(X)
        Z = [Zprev]
        for i in range(len(self.nhs)):
            V = self.Vs[i]
            Zprev = np.tanh(Zprev @ V[1:, :] + V[0:1, :])
            Z.append(Zprev)
        Y = Zprev @ self.W[1:, :] + self.W[0:1, :]
        Y = self._unstandardizeT(Y)
        return (Y, Z[1:]) if allOutputs else Y

    def getNumberOfIterations(self):
        return self.numberOfIterations

    def getErrors(self):
        return self.errorTrace

    def getTrainingTime(self):
        return self.trainingTime

    def getWeightsHistory(self):
        return self.weightsHistory

    def save(self, filename):
        pickle.dump(self, open(filename, 'wb'))

    @staticmethod
    def load(filename):
        return pickle.load(open(filename, 'rb'))

    def draw(self, inputNames=None, outputNames=None, gray=False):
        ml.draw(self.Vs, self.W, inputNames, outputNames, gray)
 

######################################################################
##  class NeuralNetworkClassifier
######################################################################

class NeuralNetworkClassifier(NeuralNetwork):

    def __init__(self, ni, nhs, no):
        NeuralNetwork.__init__(self, ni, nhs, no)

    def _multinomialize(self, Y):   # also known as softmax
        # fix to avoid overflow
        mx = max(0,np.max(Y))
        expY = np.exp(Y-mx)
        # print('mx',mx)
        denom = np.sum(expY,axis=1).reshape((-1,1)) + sys.float_info.epsilon
        Y = expY / denom
        return Y

    def _objectiveF(self, w, X, Tindicators):
        self._unpack(w)
        # Do forward pass through all layers
        Zprev = X
        for i in range(len(self.nhs)):
            V = self.Vs[i]
            Zprev = np.tanh(Zprev @ V[1:, :] + V[0:1, :])  # handling bias weight without adding column of 1's
        Y = Zprev @ self.W[1:, :] + self.W[0:1, :]
        Y = self._multinomialize(Y)
        return - np.mean(Tindicators * np.log(Y + sys.float_info.epsilon))

    def _gradientF(self, w, X, Tindicators):
        self._unpack(w)
        # Do forward pass through all layers
        Zprev = X
        Z = [Zprev]
        for i in range(len(self.nhs)):
            V = self.Vs[i]
            Zprev = np.tanh(Zprev @ V[1:, :] + V[0:1, :])
            Z.append(Zprev)
        Y = Zprev @ self.W[1:, :] + self.W[0:1, :]
        Y = self._multinomialize(Y)
        # Do backward pass, starting with delta in output layer
        delta = - (Tindicators - Y) / (X.shape[0] * Tindicators.shape[1])
        dW = np.vstack((np.ones((1, delta.shape[0])) @ delta, 
                        Z[-1].T @ delta))
        dVs = []
        delta = (1 - Z[-1]**2) * (delta @ self.W[1:, :].T)
        for Zi in range(len(self.nhs), 0, -1):
            Vi = Zi - 1  # because X is first element of Z
            dV = np.vstack((np.ones((1, delta.shape[0])) @ delta,
                            Z[Zi-1].T @ delta))
            dVs.insert(0, dV)
            delta = (delta @ self.Vs[Vi][1:, :].T) * (1 - Z[Zi-1]**2)
        return self._pack(dVs, dW)

    def train(self, X, T, nIterations=100, verbose=False,
              weightPrecision=0, errorPrecision=0, saveWeightsHistory=False):
        
        if self.Xmeans is None:
            self.Xmeans = X.mean(axis=0)
            self.Xstds = X.std(axis=0)
            self.Xconstant = self.Xstds == 0
            self.XstdsFixed = copy(self.Xstds)
            self.XstdsFixed[self.Xconstant] = 1
        X = self._standardizeX(X)

        self.classes = np.unique(T)

        if T.ndim == 1:
            T = T.reshape((-1, 1))
        Tindicators = ml.makeIndicatorVars(T)

        startTime = time.time()

        scgresult = ml.scg(self._pack(self.Vs, self.W),
                            self._objectiveF, self._gradientF,
                            X, Tindicators,
                            xPrecision=weightPrecision,
                            fPrecision=errorPrecision,
                            nIterations=nIterations,
                            verbose=verbose,
                            ftracep=True,
                            xtracep=saveWeightsHistory)

        self._unpack(scgresult['x'])
        self.reason = scgresult['reason']
        self.errorTrace = np.sqrt(scgresult['ftrace']) # * self.Tstds # to _unstandardize the MSEs
        self.numberOfIterations = len(self.errorTrace)
        self.trained = True
        self.weightsHistory = scgresult['xtrace'] if saveWeightsHistory else None
        self.trainingTime = time.time() - startTime
        return self

    def use(self, X, allOutputs=False):
        Zprev = self._standardizeX(X)
        Z = [Zprev]
        for i in range(len(self.nhs)):
            V = self.Vs[i]
            Zprev = np.tanh(Zprev @ V[1:, :] + V[0:1, :])
            Z.append(Zprev)
        Y = Zprev @ self.W[1:, :] + self.W[0:1, :]
        Y = self._multinomialize(Y)
        classes = self.classes[np.argmax(Y, axis=1)].reshape((-1, 1))
        return (classes, Y, Z[1:]) if allOutputs else classes


if __name__ == '__main__':

    X = np.arange(10).reshape((-1, 1))
    T = X + 2

    net = NeuralNetwork(1, 0, 1)
    net.train(X, T, 100)
    print(net)
    print('T, Predicted')
    print(np.hstack((T, net.use(X))))

    net = NeuralNetwork(1, [5, 5], 1)
    net.train(X, T, 200)
    print(net)
    print('T, Predicted')
    print(np.hstack((T, net.use(X))))

    Tc = np.array([1]*5 + [2]*5).reshape((-1, 1))
    netc = NeuralNetworkClassifier(X.shape[1], [5, 5], len(np.unique(Tc)))
    netc.train(X, Tc, 20)
    print(netc)
    print('Tc, Predicted')
    print(np.hstack((Tc, netc.use(X))))

    netc.save('nnetA4.pkl')

    netd = NeuralNetwork.load('nnetA4.pkl')
