'''
picobot.py

Class to encapsulate PicoBot control
'''
import time
#import picobot_motors
from picobot_motors import MotorDriver
from picobot_arm import PicoBotArm

class PicoBot:
    def __init__(self):
        #self.m = picobot_motors.MotorDriver()
        self.m = MotorDriver()
        time.sleep(1)
        print("PicoBot initialized")
        #Parameter 1: motor select:'LeftFront', 'LeftBack', 'RightFront', 'RightBack'
        #Parameter 2: turn dir:'forward', 'backward'
        #Parameter 3: motor speed: 0-100
        #Parameter 4: Running time: >0
        
        # Създаване на обект на класа
        self.arm = PicoBotArm()
        
    def stop_all_motors(self):
        self.m.StopAllMotors()
        
    def starf_left(self, speed = 50):
    # Default speed is 50    
        self.m.TurnMotor('LeftFront', 'backward', speed)
        self.m.TurnMotor('LeftBack','forward', speed) # rename to LeftRearMotor??????????
        self.m.TurnMotor('RightFront', 'forward', speed)
        self.m.TurnMotor('RightBack', 'backward', speed)

    def starf_right(self, speed = 50):
    # Default speed = 50 is 50 %    
        self.m.TurnMotor('LeftFront', 'forward', speed)
        self.m.TurnMotor('LeftBack','backward', speed)
        self.m.TurnMotor('RightFront', 'backward', speed)
        self.m.TurnMotor('RightBack', 'forward', speed)
        

    def goForward(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'forward', speed)
        self.m.TurnMotor('LeftBack','forward', speed) 
        self.m.TurnMotor('RightFront', 'forward', speed)
        self.m.TurnMotor('RightBack', 'forward', speed)
        
    def goBackwad(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'backward', speed)
        self.m.TurnMotor('LeftBack','backward', speed) 
        self.m.TurnMotor('RightFront', 'backward', speed)
        self.m.TurnMotor('RightBack', 'backward', speed)

    def moveRight(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'forward', speed)
        self.m.TurnMotor('LeftBack','backward', speed)
        self.m.TurnMotor('RightFront', 'backward', speed)
        self.m.TurnMotor('RightBack', 'forward', speed)
        
    def moveLeft(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'backward', speed)
        self.m.TurnMotor('LeftBack','forward', speed) 
        self.m.TurnMotor('RightFront', 'forward', speed)
        self.m.TurnMotor('RightBack', 'backward', speed)
        
    def moveRightForward(self, speed = 50):
        self.m.TurnMotor('LeftFront','forward', speed) 
        self.m.TurnMotor('RightBack', 'forward', speed)
        
    def moveRightBackward(self, speed = 50):
        self.m.TurnMotor('LeftBack', 'backward', speed)
        self.m.TurnMotor('RightFront', 'backward', speed)
        
    def moveLeftForward(self, speed = 50):
        self.m.TurnMotor('LeftBack','forward', speed) 
        self.m.TurnMotor('RightFront', 'forward', speed)
        
    def moveLeftBackward(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'backward', speed)
        self.m.TurnMotor('RightBack', 'backward', speed)
        
    def rotateRight(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'forward', speed)
        self.m.TurnMotor('LeftBack','forward', speed) 
        self.m.TurnMotor('RightFront', 'backward', speed)
        self.m.TurnMotor('RightBack', 'backward', speed)

    def rotateLeft(self, speed = 50):
        self.m.TurnMotor('LeftFront', 'backward', speed)
        self.m.TurnMotor('LeftBack','backward', speed) 
        self.m.TurnMotor('RightFront', 'forward', speed)
        self.m.TurnMotor('RightBack', 'forward', speed)

    def stopRobot(self, delay_ms = 10): #??? do we need delay
        self.m.StopAllMotors()
        time.sleep(delay_ms)
        
    def hardStop(self):
        self.m.StopAllMotors()
