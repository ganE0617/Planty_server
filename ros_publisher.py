import roslibpy
import time

class RGBPublisher:
    def __init__(self):
        # Initialize ROS client with WebSocket connection
        self.client = roslibpy.Ros(host='wireguard', port=9090)
        self.client.run()
        
        # Create publisher for GPIO controller commands
        self.publisher = roslibpy.Topic(
            self.client,
            '/gpio_controller/commands',
            'control_msgs/DynamicInterfaceGroupValues'
        )
        
        print('RGB Publisher has been started')

    def publish_rgb(self, r: int, g: int, b: int):
        # Create message structure
        msg = {
            'header': {
                'stamp': {
                    'sec': int(time.time()),
                    'nanosec': int((time.time() % 1) * 1e9)
                }
            },
            'interface_groups': ['neopixel'],
            'interface_values': [{
                'interface_names': ['Led R', 'Led G', 'Led B'],
                'values': [float(r), float(g), float(b)]
            }]
        }
        
        # Publish the message
        self.publisher.publish(roslibpy.Message(msg))
        print(f'Publishing RGB values: [{r}, {g}, {b}]')

    def terminate(self):
        self.client.terminate()

# Create a singleton instance
rgb_publisher = RGBPublisher()
