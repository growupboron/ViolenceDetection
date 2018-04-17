import tensorflow as tf		
import numpy as np
import settings.DeploySettings as deploySettings

class OutputSmoother:
	def __init__(self):
		self._previousPrediction = False
		self._previousOutput = False
		self._countOfNeighborResult = 0

	def Smooth(self, isFighting_):
		if isFighting_ != self._previousPrediction:
			self._countOfNeighborResult = 1
			self._previousPrediction = isFighting_

		elif isFighting_ == self._previousPrediction:
			self._countOfNeighborResult += 1
			if self._countOfNeighborResult >= deploySettings.CHANGE_JUDGEMENT_THRESHOLD:
				self._previousOutput = isFighting_
			

		return self._previousOutput


class ViolenceDetector:
	def __init__(self):
		# PlaceHolders
		self._inputPlaceholder = tf.placeholder(deploySettings.FLOAT_TYPE,
						  shape=[1, 1,
							 deploySettings.INPUT_SIZE,
							 deploySettings.INPUT_SIZE,
							 deploySettings.INPUT_CHANNELS])
		self._batchSizePlaceholder = tf.placeholder(tf.int32)
		self._unrolledSizePlaceholder = tf.placeholder(tf.int32)
		self._isTrainingPlaceholder = tf.placeholder(tf.bool)
		self._trainingStepPlaceholder = tf.placeholder(tf.int64)

		# Net
		self._net = deploySettings.GetNetwork(	self._inputPlaceholder,
							self._batchSizePlaceholder,
							self._unrolledSizePlaceholder,
							self._isTrainingPlaceholder,
							self._trainingStepPlaceholder)
		self._net.Build()
		self._predictionOp = tf.nn.softmax(self._net.logitsOp, axis=-1, name="tf.nn.softmax")
		self._listOfPreviousCellState = None

		# Session
		self.session = tf.Session()
		init = tf.global_variables_initializer()
		self.session.run(init)
		self._recoverModelFromCheckpoints()

		# Output Smoothing
		self._outputSmoother = OutputSmoother()

	def __del__(self):
		self.session.close()

	def Detect(self, netInputImage_):
		'''
		      The argument 'netInputImage_' should be shape of:
		    [deploySettings.INPUT_SIZE, deploySettings.INPUT_SIZE, deploySettings.INPUT_CHANNELS].
		    And the value of each pixel should be in the range of [-1, 1].
		      Note, if you use OpenCV to read images or videos, you should convert the Color from
		    BGR to RGB.  Moreover, the value should also be converted from [0, 255] to [-1, 1].
		'''
		inputImage = netInputImage_.reshape(self._inputPlaceholder.shape)

		inputFeedDict = { self._inputPlaceholder : inputImage,
				  self._batchSizePlaceholder : 1,
				  self._unrolledSizePlaceholder : 1,
				  self._isTrainingPlaceholder : False,
				  self._trainingStepPlaceholder : 0 }
		cellStateFeedDict = self._net.GetFeedDictOfLSTM(1, self._listOfPreviousCellState)

		inputFeedDict.update(cellStateFeedDict)

		tupleOfOutputs = self.session.run( [self._predictionOp] + self._net.GetListOfStatesTensorInLSTMs(),
			     			   feed_dict = inputFeedDict )
		listOfOutputs = list(tupleOfOutputs)
		prediction = listOfOutputs.pop(0)
		self._listOfPreviousCellState = listOfOutputs

		isFighting = np.equal(np.argmax(prediction), np.argmax(deploySettings.FIGHT_LABEL))

		smoothedOutput = self._outputSmoother.Smooth(isFighting)

		return smoothedOutput

	def _recoverModelFromCheckpoints(self):
		print("Load Pretrain model from: ", deploySettings.PATH_TO_MODEL_CHECKPOINTS)
		modelLoader = tf.train.Saver()
		modelLoader.restore(self.session, deploySettings.PATH_TO_MODEL_CHECKPOINTS)

